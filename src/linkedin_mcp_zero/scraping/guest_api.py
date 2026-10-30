from __future__ import annotations

import asyncio
import importlib
import re
import secrets
from datetime import datetime
from typing import Any

import structlog
from curl_cffi.requests import AsyncSession
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from linkedin_mcp_zero.config.defaults import DEFAULT_LIMIT, GUEST_API_BASE, MAX_LIMIT
from linkedin_mcp_zero.scraping.schema import extract_json_ld, first_job_posting
from linkedin_mcp_zero.utils.circuit_breaker import CircuitBreaker
from linkedin_mcp_zero.utils.compress import (
    clean_text,
    compact_dict,
    compact_location,
    relative_age,
    truncate,
)
from linkedin_mcp_zero.utils.errors import ParseError, UpstreamError
from linkedin_mcp_zero.utils.telemetry import trace_span

HTMLParser: Any = None
try:
    from selectolax.lexbor import LexborHTMLParser

    HTMLParser = LexborHTMLParser
except (ImportError, AttributeError):
    try:
        _mod = importlib.import_module("selectolax.parser")
        HTMLParser = getattr(_mod, "HTMLParser", None)
    except Exception:
        HTMLParser = None

logger = structlog.get_logger()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

JOB_ID_RE = re.compile(r"(?:jobs/view/|currentJobId=|jobPosting/|[-_])(\d{6,})")


class GuestAPIClient:
    def __init__(self, timeout: float = 15) -> None:
        self.timeout = timeout
        self._session: AsyncSession[Any] | None = None
        self.circuit_breaker = CircuitBreaker()
        self._in_flight: dict[str, asyncio.Future[dict[str, object]]] = {}

    async def _get_session(self) -> AsyncSession[Any]:
        if self._session is None:
            ua = secrets.choice(USER_AGENTS)
            self._session = AsyncSession(
                impersonate="chrome124",
                headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"},
                timeout=self.timeout,
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    @trace_span("guest_api.search_jobs")
    async def search_jobs(
        self,
        kw: str,
        loc: str = "",
        *,
        company: str = "",
        job_type: str = "",
        exp: int | None = None,
        remote: bool | None = None,
        age: str = "",
        sort: str = "relevance",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        self.circuit_breaker.check()
        limit = max(1, min(limit, MAX_LIMIT))
        search_kw = kw
        if company and not company.isdigit() and company.lower() not in kw.lower():
            search_kw = f"{kw} {company}".strip() if kw else company

        params: dict[str, Any] = {
            "keywords": search_kw,
            "location": loc,
            "start": 0,
        }
        if company and company.isdigit():
            params["f_C"] = company
        if job_type:
            params["f_JT"] = _job_type_code(job_type)
        if exp:
            params["f_E"] = str(exp)
        if remote is True:
            params["f_WT"] = "2"
        if age:
            params["f_TPR"] = age
        if sort == "date":
            params["sortBy"] = "DD"

        rows: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        session = await self._get_session()
        norm_co = company.strip().lower() if company else ""

        # Fetch up to 3 pages if company filtering requires more candidates to meet limit
        max_pages = min(limit * 3 if norm_co else limit, MAX_LIMIT)
        for start in range(0, max_pages, 25):
            params["start"] = start

            async def _make_request() -> Any:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    reraise=True,
                ):
                    with attempt:
                        response = await session.get(
                            f"{GUEST_API_BASE}/seeMoreJobPostings/search",
                            params=params,
                        )
                        if response.status_code >= 400:
                            new_ua = secrets.choice(USER_AGENTS)
                            session.headers["User-Agent"] = new_ua
                            self.circuit_breaker.record_failure()
                            raise UpstreamError(f"LinkedIn guest search failed: HTTP {response.status_code}")
                        self.circuit_breaker.record_success()
                        return response

            response = await _make_request()
            parsed = parse_search_results(response.text)
            if not parsed:
                break

            for r in parsed:
                jid = str(r.get("id") or "")
                if jid and jid in seen_ids:
                    continue
                if norm_co:
                    r_co = str(r.get("co") or "").lower()
                    r_t = str(r.get("t") or "").lower()
                    if norm_co not in r_co and norm_co not in r_t:
                        continue
                if jid:
                    seen_ids.add(jid)
                rows.append(r)
                if len(rows) >= limit:
                    break

            if len(rows) >= limit:
                break

        # Calculate keyword relevance score for sorting
        if kw:
            kw_tokens = [w.lower() for w in re.findall(r"\w+", kw) if len(w) > 2]
            for r in rows:
                t_tokens = set(re.findall(r"\w+", str(r.get("t", "")).lower()))
                if kw_tokens:
                    matches = sum(1 for w in kw_tokens if w in t_tokens)
                    r["relevance"] = round((matches / len(kw_tokens)) * 100)

        return rows[:limit]

    @trace_span("guest_api.get_job_details")
    async def get_job_details(self, job_id_or_url: str) -> dict[str, object]:
        self.circuit_breaker.check()
        job_id = extract_job_id(job_id_or_url)
        if job_id in self._in_flight:
            return await self._in_flight[job_id]

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, object]] = loop.create_future()
        self._in_flight[job_id] = future

        try:
            session = await self._get_session()

            async def _make_request() -> Any:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    reraise=True,
                ):
                    with attempt:
                        response = await session.get(f"{GUEST_API_BASE}/jobPosting/{job_id}")
                        if response.status_code >= 400:
                            new_ua = secrets.choice(USER_AGENTS)
                            session.headers["User-Agent"] = new_ua
                            self.circuit_breaker.record_failure()
                            raise UpstreamError(f"LinkedIn guest job details failed: HTTP {response.status_code}")
                        self.circuit_breaker.record_success()
                        return response

            response = await _make_request()
            result = parse_job_detail(response.text, job_id)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._in_flight.pop(job_id, None)


def extract_job_id(value: str) -> str:
    if value.isdigit():
        return value
    match = JOB_ID_RE.search(value)
    if not match:
        raise ParseError("Could not extract a LinkedIn job id from input")
    return match.group(1)


def parse_search_results(html: str, now: datetime | None = None) -> list[dict[str, object]]:
    parser = HTMLParser(html)
    cards = parser.css(".base-card")
    if not cards:
        cards = parser.css(".job-search-card")
    if not cards:
        cards = parser.css("li")

    results: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for card in cards:
        link = card.css_first("a.base-card__full-link, a[href*='/jobs/view/']")
        url = clean_text(link.attributes.get("href", "") if link else "")
        job_id = extract_job_id(url) if url else ""
        if not job_id:
            urn = card.attributes.get("data-entity-urn", "")
            if "urn:li:jobPosting:" in urn:
                job_id = urn.split(":")[-1]

        # Prevent duplicate jobs in same search result
        if job_id and job_id in seen_ids:
            continue
        if job_id:
            seen_ids.add(job_id)

        title = clean_text(_first_text(card, [".base-search-card__title", ".job-search-card__title", "h3"]))
        company = clean_text(_first_text(card, [".base-search-card__subtitle", ".job-search-card__subtitle", "h4"]))
        location = compact_location(
            _first_text(card, [".job-search-card__location", ".base-search-card__metadata", "span"])
        )

        posted_iso = ""
        posted_raw = ""
        time_tag = card.css_first("time")
        if time_tag:
            posted_iso = clean_text(time_tag.attributes.get("datetime", ""))
            posted_raw = posted_iso or time_tag.text().strip()

        # Extract benefits (e.g. 'Actively Hiring', 'Easy Apply')
        benefits = clean_text(_first_text(card, [".job-posting-benefits__text", ".result-benefits__text"]))

        # Extract salary if present on the search card
        sal = clean_text(_first_text(card, [".job-search-card__salary-info", ".salary"]))

        results.append(
            compact_dict(
                {
                    "id": job_id,
                    "t": title,
                    "co": company,
                    "loc": location,
                    "url": url.split("?")[0]
                    if url
                    else (f"https://www.linkedin.com/jobs/view/{job_id}" if job_id else ""),
                    "posted": posted_iso[:10] if posted_iso else "",
                    "age": relative_age(posted_raw, now),
                    "benefits": benefits,
                    "sal": sal,
                }
            )
        )
    return results


def parse_job_detail(html: str, job_id: str) -> dict[str, object]:
    parser = HTMLParser(html)
    schema = first_job_posting(extract_json_ld(html)) or {}
    title = clean_text(str(schema.get("title") or _first_text(parser, ["h1", ".top-card-layout__title"])))
    company = _schema_org_name(schema.get("hiringOrganization")) or clean_text(
        _first_text(parser, [".topcard__org-name-link", ".top-card-layout__second-subline a"])
    )
    location = _schema_org_name(schema.get("jobLocation")) or clean_text(
        _first_text(parser, [".topcard__flavor--bullet", ".top-card-layout__second-subline span"])
    )
    desc = str(schema.get("description") or _first_text(parser, [".show-more-less-html__markup"]))
    salary = _salary(schema.get("baseSalary"))
    employment = schema.get("employmentType")
    posted = str(schema.get("datePosted") or "")
    skills = _extract_skills(clean_text(desc))
    applicants = clean_text(_first_text(parser, [".num-applicants__caption", ".num-applicants__figure"]))

    return compact_dict(
        {
            "id": job_id,
            "t": title,
            "co": company,
            "loc": compact_location(location),
            "sal": salary,
            "type": _employment_type(employment),
            "posted": posted[:10],
            "age": relative_age(posted),
            "applicants": applicants,
            "skills": skills[:12],
            "desc": truncate(desc, 900),
            "url": f"https://www.linkedin.com/jobs/view/{job_id}",
        }
    )


def _first_text(node: Any, selectors: list[str]) -> str:
    for selector in selectors:
        found = node.css_first(selector)
        if found:
            return str(found.text(deep=True))
    return ""


def _schema_org_name(value: object) -> str:
    if isinstance(value, dict):
        if "name" in value:
            return clean_text(str(value["name"]))
        if "address" in value and isinstance(value["address"], dict):
            address = value["address"]
            return compact_location(
                ", ".join(
                    clean_text(str(address.get(k, "")))
                    for k in ("addressLocality", "addressRegion", "addressCountry")
                    if address.get(k)
                )
            )
    if isinstance(value, list) and value:
        return _schema_org_name(value[0])
    return ""


def _salary(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    currency = clean_text(str(value.get("currency", "")))
    amount = value.get("value")
    if not isinstance(amount, dict):
        return ""
    interval = clean_text(str(amount.get("unitText", ""))).lower()
    min_value = amount.get("minValue")
    max_value = amount.get("maxValue")
    single = amount.get("value")
    suffix = "/yr" if "year" in interval else ("/hr" if "hour" in interval else "")
    symbol = "$" if currency == "USD" else f"{currency} "
    if min_value and max_value:
        return f"{symbol}{_money(min_value)}-{_money(max_value)}{suffix}"
    if single:
        return f"{symbol}{_money(single)}{suffix}"
    return ""


def _money(value: object) -> str:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return clean_text(str(value))
    if number >= 1000:
        return f"{number / 1000:g}K"
    return f"{number:g}"


def _employment_type(value: object) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    text = clean_text(str(value)).upper()
    return {
        "FULL_TIME": "FT",
        "PART_TIME": "PT",
        "CONTRACTOR": "CT",
        "CONTRACT": "CT",
        "INTERN": "IN",
        "INTERNSHIP": "IN",
        "TEMPORARY": "TMP",
    }.get(text, text)


def _job_type_code(value: str) -> str:
    return {
        "fulltime": "F",
        "full-time": "F",
        "parttime": "P",
        "part-time": "P",
        "contract": "C",
        "internship": "I",
        "intern": "I",
        "temporary": "T",
    }.get(value.lower(), value)


def _extract_skills(text: str) -> list[str]:
    from linkedin_mcp_zero.config.skills import extract_skills_from_text

    return extract_skills_from_text(text)
