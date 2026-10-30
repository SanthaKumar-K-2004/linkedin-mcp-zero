from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
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
    def __init__(self, storage: Storage, public: PublicAPIEngine, llm_provider: Any | None = None) -> None:
        self.storage = storage
        self.public = public
        if llm_provider is None:
            from linkedin_mcp_zero.utils.llm import LLMProvider

            self.llm_provider = LLMProvider()
        else:
            self.llm_provider = llm_provider
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
        self.vector_storage = None
        try:
            from linkedin_mcp_zero.storage.vector_db import VectorStorage

            self.vector_storage = VectorStorage()
        except Exception:
            self.vector_storage = None

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

    def _reciprocal_rank_fusion(
        self,
        bm25_ranks: dict[str, int],
        dense_ranks: dict[str, int],
        k: int = 60,
        w_bm25: float = 0.4,
        w_dense: float = 0.6,
    ) -> dict[str, float]:
        """Combines BM25 and dense rank lists using Reciprocal Rank Fusion (RRF)."""
        all_ids = set(bm25_ranks.keys()) | set(dense_ranks.keys())
        scores: dict[str, float] = {}
        for item_id in all_ids:
            score = 0.0
            if item_id in bm25_ranks:
                score += w_bm25 * (1.0 / (k + bm25_ranks[item_id]))
            if item_id in dense_ranks:
                score += w_dense * (1.0 / (k + dense_ranks[item_id]))
            scores[item_id] = score
        return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))

    def evaluate_job_viability(
        self,
        job: dict[str, Any],
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assess posting freshness, applicant saturation, and ghost-job probability."""
        detail = detail or {}
        full_text = " ".join(str(v) for v in {**job, **detail}.values()).lower()

        repost_matches = re.findall(r"reposted\s*(\d*)\s*(?:times|ago)?", full_text)
        repost_count = 0
        if repost_matches:
            try:
                repost_count = int(repost_matches[0]) if repost_matches[0] else 1
            except ValueError:
                repost_count = 1

        app_matches = re.findall(r"(\d+)\s+applicants", full_text)
        applicants = int(app_matches[0]) if app_matches else 0

        viability_score = 1.0
        risk_factors: list[str] = []

        if repost_count >= 3:
            viability_score -= 0.45
            risk_factors.append(f"Reposted {repost_count} times (High ghost-job probability)")
        elif repost_count >= 1:
            viability_score -= 0.15
            risk_factors.append("Reposted listing")

        if applicants > 300:
            viability_score -= 0.35
            risk_factors.append(f"Hyper-saturated ({applicants} applicants)")
        elif applicants > 100:
            viability_score -= 0.15
            risk_factors.append(f"Moderate saturation ({applicants} applicants)")

        viability_score = max(0.1, min(1.0, viability_score))

        if viability_score >= 0.8:
            status = "ACTIVE_HIGH_PRIORITY"
        elif viability_score >= 0.5:
            status = "NORMAL_CONSIDERATION"
        elif viability_score >= 0.3:
            status = "SATURATED_LOW_YIELD"
        else:
            status = "GHOST_JOB_RISK"

        return {
            "job_id": str(job.get("id", "")),
            "viability_score": round(viability_score, 2),
            "status": status,
            "repost_count": repost_count,
            "applicants": applicants,
            "risk_factors": risk_factors,
        }

    async def analyze_job_viability(self, job_id_or_url: str) -> dict[str, Any]:
        """Public method to analyze hiring viability, saturation, and ghost-job risks."""
        try:
            detail = await self.public.get_job_details(job_id_or_url)
        except Exception as e:
            return {"error": "fetch_failed", "detail": str(e), "job_id": job_id_or_url}
        actual_id = str(detail.get("id") or job_id_or_url)
        viability = self.evaluate_job_viability({"id": actual_id}, detail)
        if str(viability.get("job_id", "")):
            self.storage.record_job_metadata(
                job_id=str(viability["job_id"]),
                applicants_count=viability.get("applicants", 0),
                repost_count=viability.get("repost_count", 0),
            )
        return {
            **viability,
            "title": detail.get("t") or detail.get("title") or "",
            "company": detail.get("co") or detail.get("company") or "",
            "location": detail.get("loc") or detail.get("location") or "",
        }

    async def match_jobs_to_resume(
        self,
        id: int,
        kw: str = "",
        loc: str = "",
        min_score: int = 60,
        limit: int = 15,
        ctx: Any | None = None,
    ) -> dict[str, Any]:
        resume = self.storage.get_resume(id)
        if not resume:
            return {"error": "resume_not_found", "id": id}
        skills = set(resume.get("skills", []))
        search_kw = kw or " ".join(list(skills)[:3]) or "software engineer"
        jobs = await self.public.search_jobs(search_kw, loc=loc, limit=limit)

        # Expand skills via in-process skill graph
        expanded_skills_map = self.storage.expand_skills(list(skills))

        import asyncio

        semaphore = asyncio.Semaphore(5)

        async def _fetch_detail(job_dict: dict[str, Any]) -> dict[str, Any]:
            jid = job_dict.get("id")
            if not jid:
                return {}
            async with semaphore:
                try:
                    return await self.public.get_job_details(str(jid))
                except Exception as e:
                    logger.warning(
                        "Failed to get job details for matching",
                        job_id=jid,
                        error=str(e),
                    )
                    return {}

        details_results = await asyncio.gather(*(_fetch_detail(job) for job in jobs))

        matches: list[dict[str, Any]] = []
        for job, detail in zip(jobs, details_results, strict=True):
            # Index into FTS5 for fast full-text querying
            if job.get("id"):
                self.storage.index_job_fts(
                    job_id=str(job["id"]),
                    title=str(job.get("t") or detail.get("title") or ""),
                    company=str(job.get("co") or detail.get("company") or ""),
                    location=str(job.get("loc") or detail.get("location") or ""),
                    description=str(detail.get("desc") or detail.get("description") or ""),
                    skills=" ".join(skills),
                )

            text = " ".join(str(v) for v in {**job, **detail}.values())
            matched = sorted(skill for skill in skills if skill.lower() in text.lower())

            # Check graph-inferred skills
            inferred_skills = []
            for src_skill, targets in expanded_skills_map.items():
                for tgt in targets:
                    if tgt.lower() in text.lower() and src_skill.lower() not in text.lower():
                        inferred_skills.append({"required": tgt, "matched_via": src_skill})

            # Evaluate job viability
            viability = self.evaluate_job_viability(job, detail)

            # Combine keyword overlap score and semantic match score
            total_skill_count = len(matched) + len(inferred_skills) * 0.75
            keyword_score = min(100, 40 + total_skill_count * 15)
            resume_text = f"{resume.get('name', '')} {resume.get('summary', '')} {' '.join(skills)}"
            semantic_sim = self._semantic_score(resume_text, text)

            # Final score is weighted average: 40% keyword overlap, 60% semantic similarity
            score = int(0.4 * keyword_score + 0.6 * (semantic_sim * 100))
            score = max(0, min(100, score))

            why_reasons: list[str] = []
            if matched:
                why_reasons.append(f"Direct match on {len(matched)} skills ({', '.join(matched[:3])})")
            if inferred_skills:
                why_reasons.append(
                    f"Inferred {len(inferred_skills)} complementary skills ({', '.join(item['required'] for item in inferred_skills[:2])})"
                )
            why_reasons.append(
                f"{viability['status'].replace('_', ' ').title()} viability ({viability['applicants']} applicants, {viability['repost_count']} reposts)"
            )
            dynamic_why = ". ".join(why_reasons) + "."

            if score >= min_score:
                matches.append(
                    {
                        "rank": len(matches) + 1,
                        **job,
                        "score": score,
                        "match_skills": matched[:8],
                        "inferred_skills": inferred_skills[:4],
                        "viability": viability,
                        "why": dynamic_why,
                    }
                )

        # Sort matches by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        # Update rank after sorting
        for idx, match in enumerate(matches):
            match["rank"] = idx + 1

        # Enrich the top 3 matches with LLM reasoning if LLM is active
        top_matches = matches[:3]
        if top_matches and (ctx is not None or self.llm_provider.api_key or self.llm_provider.openai_api_key):
            import asyncio

            async def enrich_job(match_item: dict[str, Any]) -> None:
                job_desc = match_item.get("desc", "") or match_item.get("t", "")
                prompt = f"""Analyze the fit between this candidate and this job posting:
CANDIDATE:
Name: {resume.get("name")}
Skills: {", ".join(skills)}
Summary: {resume.get("summary", "")[:200]}

JOB:
Title: {match_item.get("t")}
Company: {match_item.get("co")}
Description/Details: {job_desc[:400]}

Provide a 1-sentence explanation of why the candidate is a match and what the most critical skill gap might be."""
                try:
                    why_text = await self.llm_provider.generate(
                        prompt=prompt,
                        system_prompt="You are a recruiter summarizing job fit in exactly one sentence.",
                        ctx=ctx,
                    )
                    if why_text:
                        match_item["why"] = why_text.strip()
                except Exception as e:
                    logger.debug("Failed to enrich job match with LLM", job_id=match_item.get("id"), error=str(e))

            await asyncio.gather(*(enrich_job(m) for m in top_matches))

        return {"matches": matches, "summary": f"Found {len(matches)} matches >= {min_score}%"}

    async def compare_jobs(self, ids: list[str]) -> dict[str, Any]:
        import asyncio

        tasks = [self.public.get_job_details(job_id) for job_id in ids[:5]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        rows = []
        for job_id, result in zip(ids[:5], results, strict=True):
            if isinstance(result, dict):
                rows.append(
                    [
                        str(result.get("co") or result.get("company") or ""),
                        str(result.get("t") or result.get("title") or ""),
                        str(result.get("sal") or result.get("salary") or ""),
                        str(result.get("loc") or result.get("location") or ""),
                        str(result.get("type") or result.get("job_type") or ""),
                        str(result.get("url") or ""),
                    ]
                )
            else:
                err_str = str(result) if result is not None else "Unknown error"
                logger.warning("Failed to fetch job details for comparison", job_id=job_id, error=err_str)
                rows.append(["ERROR", f"Failed to load job {job_id}", "", "", "", ""])
        return {"columns": ["Company", "Title", "Salary", "Location", "Type", "URL"], "rows": rows}

    async def export_jobs(self, ids: list[str], fmt: str = "csv", filename: str | None = None) -> dict[str, Any]:
        import asyncio

        tasks = [self.public.get_job_details(job_id) for job_id in ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        jobs = []
        for job_id, result in zip(ids, results, strict=True):
            if isinstance(result, dict):
                jobs.append(result)
            else:
                err_str = str(result) if result is not None else "Unknown error"
                logger.warning("Failed to fetch job details for export", job_id=job_id, error=err_str)

        fmt = fmt.lower()
        if filename:
            safe_name = Path(filename).name
            file_name = safe_name if safe_name.endswith(f".{fmt}") else f"{safe_name}.{fmt}"
        else:
            file_name = f"jobs_export.{fmt}"
        path = (self.storage.exports_dir / file_name).resolve()
        if not str(path).startswith(str(self.storage.exports_dir.resolve())):
            return {"error": "invalid_filename", "filename": filename}
        if fmt == "json":
            path.write_text(json.dumps(jobs, indent=2, ensure_ascii=True), encoding="utf-8")
        elif fmt == "csv":
            _write_csv(path, jobs)
        elif fmt == "xlsx":
            return {"error": "xlsx_not_enabled", "hint": "Use fmt='csv' or fmt='json' for now."}
        else:
            return {"error": "unsupported_format", "fmt": fmt}
        return {"path": str(path), "fmt": fmt, "count": len(jobs)}


def _sanitize_csv_cell(val: Any) -> Any:
    if isinstance(val, str) and val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val}"
    return val


def _write_csv(path: Path, jobs: list[dict[str, Any]]) -> None:
    fields = ["id", "t", "co", "loc", "sal", "type", "url"]
    sanitized_jobs = []
    for job in jobs:
        row = {
            "id": job.get("id", ""),
            "t": job.get("t") or job.get("title") or "",
            "co": job.get("co") or job.get("company") or "",
            "loc": job.get("loc") or job.get("location") or "",
            "sal": job.get("sal") or job.get("salary") or "",
            "type": job.get("type") or job.get("job_type") or "",
            "url": job.get("url", ""),
        }
        sanitized_jobs.append({k: _sanitize_csv_cell(v) for k, v in row.items()})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sanitized_jobs)
