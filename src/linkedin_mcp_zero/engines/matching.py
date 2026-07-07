from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import structlog

from linkedin_mcp_zero.engines.public_api import PublicAPIEngine
from linkedin_mcp_zero.storage.db import Storage

logger = structlog.get_logger()


class MatchingEngine:
    def __init__(self, storage: Storage, public: PublicAPIEngine) -> None:
        self.storage = storage
        self.public = public

    async def match_jobs_to_resume(
        self,
        id: int,
        kw: str = "",
        loc: str = "",
        min_score: int = 60,
        limit: int = 15,
    ) -> dict[str, Any]:
        resume = self.storage.get_resume(id)
        if not resume:
            return {"error": "resume_not_found", "id": id}
        skills = set(resume.get("skills", []))
        search_kw = kw or " ".join(list(skills)[:3]) or "software engineer"
        jobs = await self.public.search_jobs(search_kw, loc=loc, limit=limit)
        matches = []
        for job in jobs:
            detail = {}
            if job.get("id"):
                try:
                    detail = await self.public.get_job_details(str(job["id"]))
                except Exception as e:
                    logger.warning(
                        "Failed to get job details for matching",
                        job_id=job["id"],
                        error=str(e),
                    )
                    detail = {}
            text = " ".join(str(v) for v in {**job, **detail}.values())
            matched = sorted(skill for skill in skills if skill.lower() in text.lower())
            score = min(100, 45 + len(matched) * 12)
            if score >= min_score:
                matches.append(
                    {
                        "rank": len(matches) + 1,
                        **job,
                        "score": score,
                        "match_skills": matched[:8],
                        "why": "Local keyword match against resume skills and job text.",
                    }
                )
        return {"matches": matches, "summary": f"Found {len(matches)} matches >= {min_score}%"}

    async def compare_jobs(self, ids: list[str]) -> dict[str, Any]:
        rows = []
        for job_id in ids[:5]:
            details = await self.public.get_job_details(job_id)
            rows.append(
                [
                    details.get("co", ""),
                    details.get("t", ""),
                    details.get("sal", ""),
                    details.get("loc", ""),
                    details.get("type", ""),
                    details.get("url", ""),
                ]
            )
        return {"columns": ["Company", "Title", "Salary", "Location", "Type", "URL"], "rows": rows}

    async def export_jobs(self, ids: list[str], fmt: str = "csv") -> dict[str, Any]:
        jobs = [await self.public.get_job_details(job_id) for job_id in ids]
        fmt = fmt.lower()
        path = self.storage.exports_dir / f"jobs_export.{fmt}"
        if fmt == "json":
            path.write_text(json.dumps(jobs, indent=2, ensure_ascii=True), encoding="utf-8")
        elif fmt == "csv":
            _write_csv(path, jobs)
        elif fmt == "xlsx":
            return {"error": "xlsx_not_enabled", "hint": "Use fmt='csv' or fmt='json' for now."}
        else:
            return {"error": "unsupported_format", "fmt": fmt}
        return {"path": str(path), "fmt": fmt, "count": len(jobs)}


def _write_csv(path: Path, jobs: list[dict[str, Any]]) -> None:
    fields = ["id", "t", "co", "loc", "sal", "type", "url"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)
