from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog
from curl_cffi.requests import AsyncSession

from linkedin_mcp_zero.config.defaults import DEFAULT_LIMIT, GUEST_API_BASE, MAX_LIMIT, USER_AGENT
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


def _dummy_parser(_html: str) -> Any:
    return None


HTMLParser: Callable[[str], Any]
try:
    from selectolax.lexbor import LexborHTMLParser

    HTMLParser = LexborHTMLParser
except (ImportError, AttributeError):
    try:
        from selectolax.parser import HTMLParser as _P

        HTMLParser = _P
    except Exception:
        HTMLParser = _dummy_parser

logger = structlog.get_logger()

JOB_ID_RE = re.compile(r"(?:jobs/view/|currentJobId=|jobPosting/|[-_])(\d{6,})")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SECONDS = 30.0


class NotFoundError(UpstreamError):
    """Raised for 404/410 so callers do not retry or trip the circuit breaker."""


def _retry_after_seconds(response: Any, default: float) -> float:
    try:
        raw = response.headers.get("Retry-After", "")
        return max(0.0, min(float(raw), MAX_RETRY_AFTER_SECONDS)) if raw else default
    except (TypeError, ValueError, AttributeError):
        return default


async def polite_get(client: GuestAPIClient, url: str, params: dict[str, Any] | None = None) -> Any:
    """GET with polite retries: only 429/5xx are retried, Retry-After is honored, 4xx fails fast."""
    session = await client._get_session()
    last_status = 0
    for attempt in range(3):
        response = await (session.get(url, params=params) if params is not None else session.get(url))
        status = int(response.status_code)
        if status < 400:
            client.circuit_breaker.record_success()
            return response
        last_status = status
        if status in (404, 410):
            raise NotFoundError(f"LinkedIn resource not found: HTTP {status}")
        if status not in RETRYABLE_STATUS:
            client.circuit_breaker.record_failure()
            raise UpstreamError(f"LinkedIn request rejected: HTTP {status}")
        client.circuit_breaker.record_failure()
        if attempt < 2:
            await asyncio.sleep(_retry_after_seconds(response, min(2.0 * (2**attempt), 10.0)))
    raise UpstreamError(f"LinkedIn request failed after retries: HTTP {last_status}")


def _is_company_id(value: str) -> bool:
    return bool(value) and value.strip().isdigit()


_STOP = {"and", "or", "the", "a", "an", "of", "for", "in", "at", "to", "with"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+#.]+", text.lower()) if t not in _STOP and len(t) > 1}


def rank_by_title_relevance(rows: list[dict[str, object]], kw: str) -> list[dict[str, object]]:
    """Stable re-rank: jobs whose title shares more query words come first. Never drops rows."""
    query = _tokens(kw)
    if not query or len(rows) < 2:
        return rows

    def score(row: dict[str, object]) -> float:
        title = _tokens(str(row.get("t", "")))
        if not title:
            return 0.0
        overlap = len(query & title) / len(query)
        return overlap

    return sorted(rows, key=lambda r: -score(r))


class GuestAPIClient:
    def __init__(self, timeout: float = 15) -> None:
        self.timeout = timeout
        self._session: AsyncSession[Any] | None = None
        self.circuit_breaker = CircuitBreaker()
        self._in_flight: dict[str, asyncio.Future[dict[str, object]]] = {}

    async def _get_session(self) -> AsyncSession[Any]:
        if self._session is None:
            self._session = AsyncSession(
                impersonate="chrome124",
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
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
        if company:
            if _is_company_id(company):
                pass
            elif company.lower() not in kw.lower():
                search_kw = f"{kw} {company}".strip() if kw else company

        params: dict[str, Any] = {
            "keywords": search_kw,
            "location": loc,
            "start": 0,
        }
        if company and _is_company_id(company):
            params["f_C"] = company.strip()
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
        want_company = "" if _is_company_id(company) else company.strip().lower()
        target = min(limit * 3, MAX_LIMIT * 2) if want_company else limit

        for start in range(0, target, 25):
            params["start"] = start
            response = await polite_get(self, f"{GUEST_API_BASE}/seeMoreJobPostings/search", params)
            parsed = parse_search_results(response.text)
            if not parsed:
                break

            for r in parsed:
                jid = str(r.get("id") or "")
                key = jid or f"{r.get('t')}|{r.get('co')}|{r.get('loc')}"
                if key in seen_ids:
                    continue
                if want_company:
                    r_co = str(r.get("co") or "").lower()
                    r_t = str(r.get("t") or "").lower()
                    if want_company not in r_co and want_company not in r_t:
                        continue
                seen_ids.add(key)
                rows.append(r)
                if len(rows) >= limit:
                    break

            if len(rows) >= limit:
                break

        # Calculate keyword relevance percentage score
        if kw:
            kw_tokens = [w.lower() for w in re.findall(r"\w+", kw) if len(w) > 2]
            for r in rows:
                t_tokens = set(re.findall(r"\w+", str(r.get("t", "")).lower()))
                if kw_tokens:
                    matches = sum(1 for w in kw_tokens if w in t_tokens)
                    r["relevance"] = round((matches / len(kw_tokens)) * 100)

        return rank_by_title_relevance(rows, kw)[:limit]

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
            response = await polite_get(self, f"{GUEST_API_BASE}/jobPosting/{job_id}")
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
            urn = str(card.attributes.get("data-entity-urn") or "")
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
