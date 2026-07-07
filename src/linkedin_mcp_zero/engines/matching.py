from __future__ import annotations

from collections import Counter
import csv
import json
import math
from pathlib import Path
import re
from typing import Any

import structlog

from linkedin_mcp_zero.engines.public_api import PublicAPIEngine
from linkedin_mcp_zero.storage.db import Storage

logger = structlog.get_logger()

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class MatchingEngine:
    def __init__(self, storage: Storage, public: PublicAPIEngine) -> None:
        self.storage = storage
        self.public = public
        self._transformer_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Load small fast model
                self._transformer_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(
                    "Failed to initialize SentenceTransformer, falling back to TF-IDF matching",
                    error=str(e),
                )

    def _semantic_score(self, text1: str, text2: str) -> float:
        if self._transformer_model:
            try:
                embeddings = self._transformer_model.encode([text1, text2], convert_to_numpy=True)
                dot = np.dot(embeddings[0], embeddings[1])
                norm0 = np.linalg.norm(embeddings[0])
                norm1 = np.linalg.norm(embeddings[1])
                if norm0 and norm1:
                    return float(dot / (norm0 * norm1))
            except Exception as e:
                logger.debug(
                    "Failed semantic embedding match, falling back to text-cosine match",
                    error=str(e),
                )

        # Pure python TF-IDF cosine similarity fallback
        words1 = re.findall(r"\w+", text1.lower())
        words2 = re.findall(r"\w+", text2.lower())
        vec1 = Counter(words1)
        vec2 = Counter(words2)
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum(vec1[w] * vec2[w] for w in intersection)
        sum1 = sum(val**2 for val in vec1.values())
        sum2 = sum(val**2 for val in vec2.values())
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        return float(numerator) / denominator if denominator else 0.0

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

            # Combine keyword overlap score and semantic match score
            keyword_score = min(100, 40 + len(matched) * 15)
            resume_text = f"{resume.get('name', '')} {resume.get('summary', '')} {' '.join(skills)}"
            semantic_sim = self._semantic_score(resume_text, text)

            # Final score is weighted average: 40% keyword overlap, 60% semantic similarity
            score = int(0.4 * keyword_score + 0.6 * (semantic_sim * 100))
            score = max(0, min(100, score))

            if score >= min_score:
                matches.append(
                    {
                        "rank": len(matches) + 1,
                        **job,
                        "score": score,
                        "match_skills": matched[:8],
                        "why": "Semantic matching with skill-profile similarity scoring.",
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
