from __future__ import annotations

import structlog

from linkedin_mcp_zero.cache.ttl_cache import TTLCache
from linkedin_mcp_zero.config.defaults import CACHE_MAX_ENTRIES, DEFAULT_LIMIT
from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.scraping.guest_api import GuestAPIClient
from linkedin_mcp_zero.utils.rate_limit import TokenBucket

logger = structlog.get_logger()


class PublicAPIEngine:
    def __init__(self, settings: Settings) -> None:
        self.client = GuestAPIClient(timeout=settings.timeout_seconds)
        self.cache: TTLCache[object] = TTLCache(
            ttl_seconds=settings.cache_ttl_seconds,
            max_entries=CACHE_MAX_ENTRIES,
        )
        self.bucket = TokenBucket(rate_per_second=1, capacity=3)

    async def close(self) -> None:
        await self.client.close()

    async def search_jobs(
        self,
        kw: str,
        loc: str = "",
        type: str = "",
        exp: int | None = None,
        remote: bool | None = None,
        age: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        key = ("search_jobs", kw, loc, type, exp, remote, age, limit)
        cached = self.cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        await self.bucket.acquire()
        result = await self.client.search_jobs(
            kw=kw,
            loc=loc,
            job_type=type,
            exp=exp,
            remote=remote,
            age=age,
            limit=limit,
        )
        self.cache.set(key, result)
        return result

    async def search_jobs_advanced(
        self,
        kw: str,
        loc: str = "",
        co: str = "",
        type: str = "",
        exp: int | None = None,
        remote: bool | None = None,
        age: str = "",
        sort: str = "relevance",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        key = ("search_jobs_advanced", kw, loc, co, type, exp, remote, age, sort, limit)
        cached = self.cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        await self.bucket.acquire()
        result = await self.client.search_jobs(
            kw=kw,
            loc=loc,
            company=co,
            job_type=type,
            exp=exp,
            remote=remote,
            age=age,
            sort=sort,
            limit=limit,
        )
        self.cache.set(key, result)
        return result

    async def get_job_details(self, id: str) -> dict[str, object]:
        key = ("get_job_details", id)
        cached = self.cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        await self.bucket.acquire()
        result = await self.client.get_job_details(id)
        self.cache.set(key, result)
        return result

    async def get_job_salary(self, id: str) -> dict[str, object]:
        details = await self.get_job_details(id)
        return {
            "id": details.get("id", id),
            "sal": details.get("sal", ""),
            "source": "schema_or_public_page" if details.get("sal") else "not_found",
        }

    async def get_company_jobs(
        self,
        co: str,
        loc: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        jobs = await self.search_jobs(kw=co, loc=loc, limit=limit)
        filtered = [job for job in jobs if co.lower() in str(job.get("co", "")).lower()]
        if not filtered and jobs:
            logger.warning("No jobs matched target company name in results, returning empty list", company=co)
        return filtered

    async def search_companies(self, kw: str, limit: int = 10) -> list[dict[str, object]]:
        jobs = await self.search_jobs(kw=kw, limit=min(max(limit * 2, 5), 50))
        seen: dict[str, dict[str, object]] = {}
        for job in jobs:
            company = str(job.get("co", "")).strip()
            if not company:
                continue
            current = seen.setdefault(
                company.lower(),
                {"name": company, "open_jobs": 0, "sample_roles": [], "loc": job.get("loc", "")},
            )
            current["open_jobs"] = int(current["open_jobs"]) + 1
            roles = current["sample_roles"]
            if isinstance(roles, list) and job.get("t") and len(roles) < 3:
                roles.append(job["t"])
        return list(seen.values())[:limit]

    async def get_company_profile(self, co: str) -> dict[str, object]:
        jobs = await self.get_company_jobs(co=co, limit=10)
        locations = sorted({str(job.get("loc", "")) for job in jobs if job.get("loc")})
        roles = [job.get("t", "") for job in jobs[:5]]
        return {
            "name": co,
            "source": "public_jobs_inference",
            "open_jobs_seen": len(jobs),
            "loc": locations[:5],
            "sample_roles": roles,
            "note": "Public profile enrichment is inferred from public job listings only.",
        }

    async def get_job_trends(self, kw: str, loc: str = "") -> dict[str, object]:
        jobs = await self.search_jobs(kw=kw, loc=loc, limit=50)
        companies: dict[str, int] = {}
        locations: dict[str, int] = {}
        for job in jobs:
            co = str(job.get("co", ""))
            location = str(job.get("loc", ""))
            if co:
                companies[co] = companies.get(co, 0) + 1
            if location:
                locations[location] = locations.get(location, 0) + 1
        return {
            "kw": kw,
            "loc": loc,
            "sample": len(jobs),
            "top_companies": _top_counts(companies),
            "top_locations": _top_counts(locations),
            "remote_pct": _remote_pct(jobs),
        }

    async def get_industry_insights(self, ind: str) -> dict[str, object]:
        jobs = await self.search_jobs(kw=ind, limit=50)
        role_counts: dict[str, int] = {}
        skill_counts: dict[str, int] = {}
        for job in jobs[:20]:
            title = str(job.get("t", ""))
            if title:
                role_counts[title] = role_counts.get(title, 0) + 1
            if job.get("id"):
                try:
                    details = await self.get_job_details(str(job["id"]))
                except Exception as e:
                    logger.warning(
                        "Failed to fetch job details for industry insights",
                        job_id=job["id"],
                        error=str(e),
                    )
                    details = {}
                for skill in details.get("skills", []):
                    text = str(skill)
                    skill_counts[text] = skill_counts.get(text, 0) + 1
        return {
            "industry": ind,
            "sample": len(jobs),
            "top_roles": _top_counts(role_counts),
            "in_demand_skills": [row["name"] for row in _top_counts(skill_counts)],
        }


def _top_counts(values: dict[str, int], limit: int = 5) -> list[dict[str, object]]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(values.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _remote_pct(jobs: list[dict[str, object]]) -> int:
    if not jobs:
        return 0
    remote = sum(1 for job in jobs if "remote" in str(job.get("loc", "")).lower())
    return round(remote / len(jobs) * 100)
