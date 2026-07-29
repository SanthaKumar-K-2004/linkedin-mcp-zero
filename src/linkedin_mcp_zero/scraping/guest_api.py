from __future__ import annotations

import random
import re
from datetime import datetime
from typing import Any

import structlog
from curl_cffi.requests import AsyncSession
from selectolax.parser import HTMLParser
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from linkedin_mcp_zero.config.defaults import DEFAULT_LIMIT, GUEST_API_BASE, MAX_LIMIT, TYPEAHEAD_BASE
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
from linkedin_mcp_zero.utils.skills import match_skills
from linkedin_mcp_zero.utils.telemetry import trace_span

logger = structlog.get_logger()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

JOB_ID_RE = re.compile(r"(?:jobs/view/|currentJobId=|jobPosting/|[-_])(\d{6,})")

# Friendly recency aliases mapped to LinkedIn f_TPR codes.
AGE_CODES = {
    "": "",
    "any": "",
    "24h": "r86400",
    "1d": "r86400",
    "day": "r86400",
    "7d": "r604800",
    "1w": "r604800",
    "week": "r604800",
    "30d": "r2592000",
    "1m": "r2592000",
    "month": "r2592000",
}

# f_WT: 1 on-site, 2 remote, 3 hybrid.
WORK_MODEL_CODES = {"": "", "onsite": "1", "on-site": "1", "remote": "2", "hybrid": "3"}


class GuestAPIClient:
    def __init__(self, timeout: float = 15, proxy: str | None = None) -> None:
        self.timeout = timeout
        self.proxy = proxy
        self._session: AsyncSession[Any] | None = None
        self.circuit_breaker = CircuitBreaker()
        self._company_id_cache: dict[str, str | None] = {}
        self._geo_id_cache: dict[str, str | None] = {}

    async def _get_session(self) -> AsyncSession[Any]:
        if self._session is None:
            ua = random.choice(USER_AGENTS)
            self._session = AsyncSession(
                impersonate="chrome124",
                headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"},
                timeout=self.timeout,
                proxy=self.proxy,
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _get(self, url: str, params: dict[str, Any], error_label: str) -> Any:
        session = await self._get_session()

        async def _make_request() -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                reraise=True,
            ):
                with attempt:
                    response = await session.get(url, params=params)
                    if response.status_code >= 400:
                        new_ua = random.choice(USER_AGENTS)
                        session.headers["User-Agent"] = new_ua
                        # Only upstream-hostile statuses count against the
                        # circuit breaker. A 404 (expired job id) or 400 (bad
                        # params) is a *request* problem — counting it would
                        # let a couple of bad ids block every other user of
                        # this client for 30 s.
                        if response.status_code in (403, 429) or response.status_code >= 500:
                            self.circuit_breaker.record_failure()
                        raise UpstreamError(f"{error_label}: HTTP {response.status_code}")
                    self.circuit_breaker.record_success()
                    return response

        return await _make_request()

    @trace_span("guest_api.search_jobs")
    async def search_jobs(
        self,
        kw: str,
        loc: str = "",
        *,
        company_id: str = "",
        geo_id: str = "",
        distance: int | None = None,
        job_type: str = "",
        exp: int | None = None,
        remote: bool | None = None,
        work_model: str = "",
        easy_apply: bool = False,
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
        if company_id:
            # f_C requires LinkedIn's numeric company id; resolve names via
            # resolve_company_id() before calling.
            params["f_C"] = company_id
        if geo_id:
            # Numeric geoId pins the search to a place unambiguously (unlike
            # free-text locations: "Cambridge" UK vs MA, "Portland" OR vs ME).
            params["geoId"] = geo_id
        if distance and distance > 0:
            # Search radius in miles around loc/geoId (LinkedIn default: 25).
            params["distance"] = str(min(distance, 100))
        if job_type:
            params["f_JT"] = _job_type_code(job_type)
        if exp:
            params["f_E"] = str(exp)
        model_code = WORK_MODEL_CODES.get(work_model.lower(), "")
        if model_code:
            params["f_WT"] = model_code
        elif remote is True:
            params["f_WT"] = "2"
        elif remote is False:
            params["f_WT"] = "1"
        if easy_apply:
            params["f_AL"] = "true"
        age_code = AGE_CODES.get(age.lower().strip(), age)
        if age_code:
            params["f_TPR"] = age_code
        if sort == "date":
            params["sortBy"] = "DD"

        rows: list[dict[str, object]] = []
        start = 0
        # Advance the offset by the number of rows actually returned: the
        # guest endpoint may cap a page at 10 or 25 results depending on the
        # query, and assuming a fixed page size would silently skip jobs.
        while len(rows) < limit:
            params["start"] = start
            response = await self._get(
                f"{GUEST_API_BASE}/seeMoreJobPostings/search",
                params,
                "LinkedIn guest search failed",
            )
            parsed = parse_search_results(response.text)
            if not parsed:
                break
            rows.extend(parsed)
            start += len(parsed)
        return rows[:limit]

    @trace_span("guest_api.get_job_details")
    async def get_job_details(self, job_id_or_url: str) -> dict[str, object]:
        self.circuit_breaker.check()
        job_id = extract_job_id(job_id_or_url)
        response = await self._get(
            f"{GUEST_API_BASE}/jobPosting/{job_id}",
            {},
            "LinkedIn guest job details failed",
        )
        return parse_job_detail(response.text, job_id)

    @trace_span("guest_api.typeahead")
    async def typeahead(self, query: str, kind: str = "COMPANY") -> list[dict[str, str]]:
        """Resolve a free-text name to LinkedIn entities via the typeahead API.

        kind="COMPANY" returns companies with numeric ids usable as f_C;
        kind="GEO" returns places with geoIds usable as the `geoId` param.
        """
        query = query.strip()
        if not query:
            return []
        params: dict[str, Any] = {"query": query}
        if kind.upper() == "GEO":
            params.update({"origin": "jserp", "typeaheadType": "GEO", "geoTypes": "POPULATED_PLACE"})
        else:
            params.update({"typeaheadType": "COMPANY"})
        try:
            response = await self._get(TYPEAHEAD_BASE, params, "LinkedIn typeahead failed")
        except Exception as exc:
            logger.debug("Typeahead request failed", query=query, kind=kind, error=str(exc))
            return []
        return _parse_typeahead(response.text, kind)

    async def resolve_company_id(self, name: str) -> str | None:
        """Best-effort resolution of a company name to a numeric f_C id."""
        key = name.strip().lower()
        if not key:
            return None
        if key.isdigit():
            return key
        if key in self._company_id_cache:
            return self._company_id_cache[key]
        hits = await self.typeahead(name, "COMPANY")
        chosen = _best_hit_id(hits, key)
        self._company_id_cache[key] = chosen
        return chosen

    async def resolve_geo_id(self, place: str) -> str | None:
        """Best-effort resolution of a place name to a numeric geoId."""
        key = place.strip().lower()
        if not key:
            return None
        if key.isdigit():
            return key
        if key in self._geo_id_cache:
            return self._geo_id_cache[key]
        hits = await self.typeahead(place, "GEO")
        chosen = _best_hit_id(hits, key)
        self._geo_id_cache[key] = chosen
        return chosen


def _best_hit_id(hits: list[dict[str, str]], query_key: str) -> str | None:
    """Pick a typeahead hit id, preferring an exact case-insensitive name match."""
    exact = [hit for hit in hits if hit.get("name", "").lower() == query_key and hit.get("id")]
    if exact:
        return exact[0]["id"]
    if hits and hits[0].get("id"):
        return hits[0]["id"]
    return None


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
    salary_source = "schema" if salary else ""
    if not salary:
        # Many postings carry compensation only inside the description text.
        desc_salary = _desc_salary(clean_text(desc))
        if desc_salary:
            salary = desc_salary
            salary_source = "desc"
    employment = schema.get("employmentType")
    posted = str(schema.get("datePosted") or "")
    skills = match_skills(clean_text(desc))
    applicants = _applicants(parser)
    # Every LinkedIn job detail page embeds a criteria list (Seniority level /
    # Employment type / Job function / Industries) that the JSON-LD schema
    # usually omits — mine it for structured fields otherwise unavailable.
    criteria = _job_criteria(parser)
    criteria_etype = criteria.pop("etype", "")
    job_type = _employment_type(employment) or _employment_type(criteria_etype)
    return compact_dict(
        {
            "id": job_id,
            "t": title,
            "co": company,
            "loc": compact_location(location),
            "sal": salary,
            "sal_src": salary_source,
            "type": job_type,
            "posted": posted[:10],
            "age": relative_age(posted),
            "skills": skills[:12],
            "appl": applicants,
            "cr": criteria,
            "desc": truncate(desc, 900),
            "url": f"https://www.linkedin.com/jobs/view/{job_id}",
        }
    )


_CRITERIA_KINDS = {
    "seniority level": "sen",
    "employment type": "etype",
    "job function": "func",
    "industries": "ind",
}


def _job_criteria(parser: Any) -> dict[str, str]:
    """Extract the structured job-criteria list (seniority, function, …)."""
    out: dict[str, str] = {}
    for item in parser.css(".description__job-criteria-item"):
        header = item.css_first("h3")
        value = item.css_first("span")
        if not header or not value:
            continue
        key = _CRITERIA_KINDS.get(clean_text(str(header.text(deep=True))).lower())
        if key:
            text = clean_text(str(value.text(deep=True)))
            if text:
                out[key] = truncate(text, 60)
    return out


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
    # Schema values arrive as FULL_TIME, criteria text as "Full-time" —
    # normalize both to an underscore key before lookup.
    text = clean_text(str(value or "")).upper().replace("-", "_").replace(" ", "_")
    if not text:
        # Unknown/absent types previously leaked the literal string "NONE".
        return ""
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


_APPLICANTS_RE = re.compile(r"([\d,]+)\s*\+?\s*applicants?", re.IGNORECASE)

# Salary-in-description patterns, most specific first:
#   $120,000 - $150,000 | $120K-$150K | $120K to $150K | $45-$55/hr | $45.00/hour
_SALARY_PATTERNS = [
    re.compile(
        r"\$\d{1,3}(?:,\d{3})+(?:\s*(?:-|–|—|to)\s*\$\d{1,3}(?:,\d{3})+)?"
        r"(?:\s*(?:USD\s*)?(?:a|per)\s*(?:year|yr))?"
    ),
    re.compile(r"\$\d{2,3}[Kk](?:\s*(?:-|–|—|to)\s*\$\d{2,3}[Kk])?(?:\s*(?:a|per)\s*(?:year|yr))?"),
    re.compile(r"\$\d{2,3}(?:\.\d{1,2})?(?:\s*(?:-|–|—|to)\s*\$\d{2,3}(?:\.\d{1,2})?)?\s*(?:/|per\s*)\s*(?:hr|hour)"),
]


_SALARY_CONTEXT_RE = re.compile(r"salary|compensation|\bpay\b|\bbase\b|\bofte?r\b|\bwage\b", re.IGNORECASE)


def _desc_salary(text: str) -> str:
    """Best-effort salary extraction from free-text job descriptions.

    A match is accepted outright when it is a range or carries an interval
    suffix ("... - $150,000", "$45/hr", "$120K a year"). A bare single figure
    ("$5,000") is only accepted with nearby compensation context, so phrases
    like "save $5,000 on equipment" do not masquerade as pay.
    """
    for pattern in _SALARY_PATTERNS:
        for match in pattern.finditer(text):
            snippet = match.group(0)
            explicit = (
                "-" in snippet
                or "–" in snippet
                or "—" in snippet
                or " to " in snippet.lower()
                or "/" in snippet
                or "year" in snippet.lower()
                or "yr" in snippet.lower()
                or "hour" in snippet.lower()
                or "hr" in snippet.lower()
            )
            if not explicit:
                start = max(0, match.start() - 80)
                end = min(len(text), match.end() + 80)
                if not _SALARY_CONTEXT_RE.search(text[start:end]):
                    continue
            return truncate(snippet, 60)
    return ""


def _applicants(parser: HTMLParser) -> str:
    """Extract applicant volume from the job criteria/top card when present."""
    for selector in (".num-applicants__caption", ".num-applicants__figure", "figcaption"):
        node = parser.css_first(selector)
        if not node:
            continue
        text = clean_text(node.text(deep=True))
        match = _APPLICANTS_RE.search(text)
        if match:
            number = match.group(1).replace(",", "")
            return f"{number}+" if "over" in text.lower() else number
    return ""


def _parse_typeahead(body: str, kind: str) -> list[dict[str, str]]:
    """Parse typeahead responses defensively across known payload shapes."""
    import json

    hits: list[dict[str, str]] = []
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return hits

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            identifier = node.get("id") or node.get("entityId") or node.get("geoId")
            urn = str(node.get("urn") or node.get("entityUrn") or "")
            if identifier is None and urn:
                urn_match = re.search(r"(\d{2,})\s*$", urn)
                if urn_match:
                    identifier = urn_match.group(1)
            name = node.get("name") or node.get("title") or node.get("text") or node.get("displayName")
            inner = node.get("company") or node.get("geo")
            if name is None and isinstance(inner, dict):
                name = inner.get("name")
            if identifier and name:
                hits.append({"id": str(identifier), "name": clean_text(str(name))})
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for hit in hits:
        key = f"{hit['id']}|{hit['name'].lower()}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique[:10]
