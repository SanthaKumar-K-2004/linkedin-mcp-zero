from __future__ import annotations

import random
import re
from datetime import datetime
from typing import Any

import structlog
from curl_cffi.requests import AsyncSession
from selectolax.parser import HTMLParser
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
        self._session: AsyncSession | None = None
        self.circuit_breaker = CircuitBreaker()

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            ua = random.choice(USER_AGENTS)
            self._session = AsyncSession(
                impersonate="chrome110",
                headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"},
                timeout=self.timeout,
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

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
        params: dict[str, Any] = {
            "keywords": kw,
            "location": loc,
            "start": 0,
        }
        if company:
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
        session = await self._get_session()

        for start in range(0, limit, 25):
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
                            new_ua = random.choice(USER_AGENTS)
                            session.headers["User-Agent"] = new_ua
                            self.circuit_breaker.record_failure()
                            raise UpstreamError(f"LinkedIn guest search failed: HTTP {response.status_code}")
                        self.circuit_breaker.record_success()
                        return response

            response = await _make_request()
            parsed = parse_search_results(response.text)
            rows.extend(parsed)
            if len(parsed) == 0 or len(rows) >= limit:
                break
        return rows[:limit]

    async def get_job_details(self, job_id_or_url: str) -> dict[str, object]:
        self.circuit_breaker.check()
        job_id = extract_job_id(job_id_or_url)
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
                        new_ua = random.choice(USER_AGENTS)
                        session.headers["User-Agent"] = new_ua
                        self.circuit_breaker.record_failure()
                        raise UpstreamError(f"LinkedIn guest job details failed: HTTP {response.status_code}")
                    self.circuit_breaker.record_success()
                    return response

        response = await _make_request()
        return parse_job_detail(response.text, job_id)
        return parse_job_detail(response.text, job_id)


def extract_job_id(value: str) -> str:
    if value.isdigit():
        return value
    match = JOB_ID_RE.search(value)
    if not match:
        raise ParseError("Could not extract a LinkedIn job id from input")
    return match.group(1)


def parse_search_results(html: str, now: datetime | None = None) -> list[dict[str, object]]:
    parser = HTMLParser(html)
    cards = parser.css(".base-card, .job-search-card")
    results: list[dict[str, object]] = []
    for card in cards:
        title = clean_text(_first_text(card, [".base-search-card__title", ".job-search-card__title", "h3"]))
        company = clean_text(_first_text(card, [".base-search-card__subtitle", ".job-search-card__subtitle", "h4"]))
        location = compact_location(
            _first_text(card, [".job-search-card__location", ".base-search-card__metadata", "span"])
        )
        link = card.css_first("a.base-card__full-link, a[href*='/jobs/view/']")
        url = clean_text(link.attributes.get("href", "") if link else "")
        job_id = extract_job_id(url) if url else ""
        posted = ""
        time_tag = card.css_first("time")
        if time_tag:
            posted = time_tag.attributes.get("datetime") or time_tag.text()
        results.append(
            compact_dict(
                {
                    "id": job_id,
                    "t": title,
                    "co": company,
                    "loc": location,
                    "url": url.split("?")[0] if url else "",
                    "age": relative_age(posted, now),
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
            "skills": skills[:12],
            "desc": truncate(desc, 900),
            "url": f"https://www.linkedin.com/jobs/view/{job_id}",
        }
    )


def _first_text(node: Any, selectors: list[str]) -> str:
    for selector in selectors:
        found = node.css_first(selector)
        if found:
            return found.text(deep=True, separator=" ")
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
        number = float(value)
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
    known = [
        "Python",
        "JavaScript",
        "TypeScript",
        "React",
        "Node",
        "SQL",
        "AWS",
        "Azure",
        "GCP",
        "Docker",
        "Kubernetes",
        "Django",
        "FastAPI",
        "Machine Learning",
        "AI",
        "LLM",
    ]
    lower = text.lower()
    return [skill for skill in known if skill.lower() in lower]
