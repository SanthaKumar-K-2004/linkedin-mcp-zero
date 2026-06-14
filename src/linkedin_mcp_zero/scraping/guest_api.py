from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from linkedin_mcp_zero.config.defaults import DEFAULT_LIMIT, GUEST_API_BASE, MAX_LIMIT, USER_AGENT
from linkedin_mcp_zero.scraping.schema import extract_json_ld, first_job_posting
from linkedin_mcp_zero.utils.compress import (
    clean_text,
    compact_dict,
    compact_location,
    relative_age,
    truncate,
)
from linkedin_mcp_zero.utils.errors import ParseError, UpstreamError

JOB_ID_RE = re.compile(r"(?:jobs/view/|currentJobId=|jobPosting/|[-_])(\d{6,})")


class GuestAPIClient:
    def __init__(self, timeout: float = 15) -> None:
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            timeout=timeout,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

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
        for start in range(0, limit, 25):
            params["start"] = start
            response = await self._client.get(
                f"{GUEST_API_BASE}/seeMoreJobPostings/search",
                params=params,
            )
            if response.status_code >= 400:
                raise UpstreamError(f"LinkedIn guest search failed: HTTP {response.status_code}")
            parsed = parse_search_results(response.text)
            rows.extend(parsed)
            if len(parsed) == 0 or len(rows) >= limit:
                break
        return rows[:limit]

    async def get_job_details(self, job_id_or_url: str) -> dict[str, object]:
        job_id = extract_job_id(job_id_or_url)
        response = await self._client.get(f"{GUEST_API_BASE}/jobPosting/{job_id}")
        if response.status_code >= 400:
            raise UpstreamError(f"LinkedIn guest job details failed: HTTP {response.status_code}")
        return parse_job_detail(response.text, job_id)


def extract_job_id(value: str) -> str:
    if value.isdigit():
        return value
    match = JOB_ID_RE.search(value)
    if not match:
        raise ParseError("Could not extract a LinkedIn job id from input")
    return match.group(1)


def parse_search_results(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(".base-card, .job-search-card")
    results: list[dict[str, object]] = []
    for card in cards:
        title = clean_text(
            _first_text(card, [".base-search-card__title", ".job-search-card__title", "h3"])
        )
        company = clean_text(
            _first_text(card, [".base-search-card__subtitle", ".job-search-card__subtitle", "h4"])
        )
        location = compact_location(
            _first_text(card, [".job-search-card__location", ".base-search-card__metadata", "span"])
        )
        link = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
        url = clean_text(link.get("href") if link else "")
        job_id = extract_job_id(url) if url else ""
        posted = ""
        time_tag = card.select_one("time")
        if time_tag:
            posted = time_tag.get("datetime") or time_tag.get_text()
        results.append(
            compact_dict(
                {
                    "id": job_id,
                    "t": title,
                    "co": company,
                    "loc": location,
                    "url": url.split("?")[0] if url else "",
                    "age": relative_age(posted),
                }
            )
        )
    return results


def parse_job_detail(html: str, job_id: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "lxml")
    schema = first_job_posting(extract_json_ld(html)) or {}
    title = clean_text(
        str(schema.get("title") or _first_text(soup, ["h1", ".top-card-layout__title"]))
    )
    company = _schema_org_name(schema.get("hiringOrganization")) or clean_text(
        _first_text(soup, [".topcard__org-name-link", ".top-card-layout__second-subline a"])
    )
    location = _schema_org_name(schema.get("jobLocation")) or clean_text(
        _first_text(soup, [".topcard__flavor--bullet", ".top-card-layout__second-subline span"])
    )
    desc = str(schema.get("description") or _first_text(soup, [".show-more-less-html__markup"]))
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
        found = node.select_one(selector)
        if found:
            return found.get_text(" ")
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
