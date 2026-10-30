from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog
from docx import Document
from platformdirs import user_data_dir

from linkedin_mcp_zero.config.defaults import DATA_DIR_NAME
from linkedin_mcp_zero.config.skills import COMMON_SKILLS, extract_skills_from_text
from linkedin_mcp_zero.storage.db import Storage
from linkedin_mcp_zero.utils.compress import clean_text, compact_dict, truncate

logger = structlog.get_logger()

try:
    from docling.document_converter import DocumentConverter

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
SKILLS = COMMON_SKILLS

DOMAIN_ECOSYSTEMS: dict[str, list[str]] = {
    "backend": [
        "Python",
        "SQL",
        "Docker",
        "Kubernetes",
        "AWS",
        "FastAPI",
        "PostgreSQL",
        "Redis",
        "Linux",
        "Java",
        "Go",
    ],
    "frontend": ["JavaScript", "TypeScript", "React", "Next.js", "HTML", "CSS", "Tailwind", "Redux", "GraphQL", "Vite"],
    "devops_cloud": ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux", "Azure", "GCP", "Ansible", "Helm"],
    "data_ai": [
        "Python",
        "SQL",
        "Machine Learning",
        "Pandas",
        "PyTorch",
        "TensorFlow",
        "Spark",
        "Airflow",
        "dbt",
        "NumPy",
    ],
    "mobile": ["Swift", "Kotlin", "React Native", "Flutter", "Dart", "iOS", "Android"],
    "systems": ["Rust", "C++", "C", "Linux", "Unix", "eBPF", "gRPC", "Docker"],
}


def _infer_domain_ecosystem(skills: list[str]) -> set[str]:
    sk_lower = {s.lower() for s in skills}
    best_domain = "backend"
    best_score = 0
    for domain, domain_skills in DOMAIN_ECOSYSTEMS.items():
        overlap = sum(1 for s in domain_skills if s.lower() in sk_lower)
        if overlap > best_score:
            best_score = overlap
            best_domain = domain
    return set(DOMAIN_ECOSYSTEMS[best_domain])


class ResumeEngine:
    def __init__(self, storage: Storage, public: Any | None = None, llm_provider: Any | None = None) -> None:
        self.storage = storage
        self.public = public
        if llm_provider is None:
            from linkedin_mcp_zero.utils.llm import LLMProvider

            self.llm_provider = LLMProvider()
        else:
            self.llm_provider = llm_provider

    def analyze_resume(self, path: str) -> dict[str, Any]:
        settings = self.storage.settings
        allowed = []
        if settings.allowed_resume_dirs:
            allowed = [Path(d).expanduser().resolve() for d in settings.allowed_resume_dirs]
        else:
            allowed = [
                Path.home() / "Documents",
                Path.home() / "Downloads",
                Path("/tmp"),  # nosec B108
            ]
            if settings.data_dir:
                allowed.append(Path(settings.data_dir).expanduser().resolve())
            else:
                allowed.append(Path(user_data_dir(DATA_DIR_NAME)).expanduser().resolve())
            allowed.append(Path.cwd().resolve())

        text = extract_resume_text(path, allowed_dirs=allowed)
        email = _first_match(EMAIL_RE, text)
        phone = _first_match(PHONE_RE, text)
        skills = extract_skills_from_text(text, SKILLS)
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        name = lines[0] if lines else ""
        data = compact_dict(
            {
                "name": name,
                "email": email,
                "phone": phone,
                "skills": skills,
                "summary": truncate(text, 700),
                "chars": len(text),
            }
        )
        resume_id = self.storage.save_resume(path, data)
        return {"id": resume_id, **data}

    async def get_resume_insights(self, id: int, ctx: Any | None = None) -> dict[str, Any]:
        resume = self.storage.get_resume(id)
        if not resume:
            return {"error": "resume_not_found", "id": id}

        candidate_skills = list(resume.get("skills", []))
        candidate_skill_set = {s.lower() for s in candidate_skills}
        name = resume.get("name", "Candidate")
        summary = resume.get("summary", "")

        # Formulate query from candidate's actual skills or summary
        search_query = " ".join(candidate_skills[:3]) if candidate_skills else "software engineer"

        # Expand skills via in-process learned skill graph
        expanded_skills_map = self.storage.expand_skills(candidate_skills)
        inferred_skills = {target.lower() for targets in expanded_skills_map.values() for target in targets}

        live_skill_counts: dict[str, int] = {}
        live_sample_size = 0

        # Perform real-time live labor market research if public API engine is attached
        if self.public is not None:
            try:
                live_jobs = await self.public.search_jobs(kw=search_query, limit=20)
                live_sample_size = len(live_jobs)
                for job in live_jobs:
                    job_text = f"{job.get('t', '')} {job.get('co', '')} {job.get('loc', '')} {job.get('desc', '')}"
                    for sk in extract_skills_from_text(job_text):
                        live_skill_counts[sk] = live_skill_counts.get(sk, 0) + 1
            except Exception as e:
                logger.warning(
                    "Real-time live job search for resume insights failed, falling back to graph taxonomy", error=str(e)
                )

        if live_skill_counts:
            # Sorted by real market frequency in active job listings
            market_demanded_skills = [
                sk for sk, _ in sorted(live_skill_counts.items(), key=lambda item: item[1], reverse=True)
            ]
            strengths = [sk for sk in market_demanded_skills if sk.lower() in candidate_skill_set][:8]
            # Remaining skills candidate has that weren't in top market list
            extra_strengths = [sk for sk in candidate_skills if sk.lower() not in {s.lower() for s in strengths}]
            strengths.extend(extra_strengths[: max(0, 8 - len(strengths))])

            gap_skills = [
                sk
                for sk in market_demanded_skills
                if sk.lower() not in candidate_skill_set and sk.lower() not in inferred_skills
            ][:8]

            suggestions = []
            if gap_skills:
                top_gaps = "', '".join(gap_skills[:2])
                suggestions.append(
                    f"High-frequency market requirement: consider highlighting or building experience with '{top_gaps}'."
                )
            if len(candidate_skills) < 6:
                suggestions.append(
                    "Enrich the technical skills section with specific tooling, databases, and frameworks used in production."
                )
            suggestions.append(
                f"Mirror active posting requirements for '{search_query}' by quantifying measurable business impact."
            )

            match_ratio = len(strengths) / max(len(market_demanded_skills[:8]), 1)
            if match_ratio >= 0.6:
                market_pos = f"Strong alignment for active '{search_query}' listings based on real-time market sample ({live_sample_size} jobs)."
            elif match_ratio >= 0.3:
                market_pos = f"Moderate competitive position for '{search_query}'. Closing top gap skills will expand interview conversion."
            else:
                market_pos = (
                    f"Developing alignment for '{search_query}'. Target foundational technologies currently in demand."
                )
        else:
            # Domain ecosystem and dynamic graph fallback
            ecosystem_skills = _infer_domain_ecosystem(candidate_skills)
            all_related = set()
            for sk in candidate_skills:
                info = self.storage.get_skill_cluster(sk)
                all_related.update(info.get("related_skills", []))

            all_target = ecosystem_skills | all_related
            gap_skills = sorted(all_target - {s.title() for s in candidate_skills} - set(candidate_skills))[:8]
            strengths = sorted(candidate_skills)[:8]
            suggestions = [
                "Quantify project impact with measurable latency, cost, and scale metrics.",
                "Align resume terminology with domain ecosystem and in-process skill graph co-occurrences.",
                "Detail production architecture decisions near the top of the resume.",
            ]
            market_pos = "Evaluated via dynamic domain ecosystem and in-process skill graph."

        insights: dict[str, Any] = {
            "id": id,
            "target_query": search_query,
            "market_sample_jobs": live_sample_size,
            "gap_skills": gap_skills,
            "strengths": strengths,
            "inferred_skills": [tgt for tgts in expanded_skills_map.values() for tgt in tgts][:6],
            "suggestions": suggestions,
            "market_pos": market_pos,
        }

        # If LLM is available, enrich with AI reasoning
        if ctx is not None or self.llm_provider.api_key or self.llm_provider.openai_api_key:
            prompt = f"""Analyze this candidate's resume and real-time market fit:
Candidate Name: {name}
Current Skills: {", ".join(candidate_skills)}
Market Target: {search_query}
Live Market Gaps: {", ".join(gap_skills)}
Summary: {summary}

Provide:
1. Executive Summary
2. Top 3 Strengths
3. Recommended improvements and missing skills
4. Key suggestions to stand out in the current job market"""
            try:
                analysis = await self.llm_provider.generate(
                    prompt=prompt,
                    system_prompt="You are a professional resume reviewer. Be structured and concise.",
                    ctx=ctx,
                )
                insights["llm_insights"] = analysis
                insights["market_pos"] = "AI-Powered Live Analysis"
            except Exception as e:
                logger.warning("LLM resume insights generation failed, using real-time market data only", error=str(e))

        return insights


def extract_resume_text(path: str, allowed_dirs: list[Path] | None = None) -> str:
    file = Path(path).expanduser().resolve()

    if allowed_dirs is None:
        allowed_dirs = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path("/tmp"),  # nosec B108
            Path.cwd().resolve(),
        ]

    is_allowed = False
    for allowed_dir in allowed_dirs:
        try:
            resolved_dir = allowed_dir.resolve()
            file.relative_to(resolved_dir)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        raise ValueError(
            f"Resume path '{path}' is outside allowed directories. "
            f"Allowed directories: {[str(d) for d in allowed_dirs]}"
        )

    if not file.exists():
        raise FileNotFoundError(f"Resume not found: {path}")

    suffix = file.suffix.lower()
    if suffix in {".txt", ".md"}:
        return file.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        if DOCLING_AVAILABLE:
            try:
                converter = DocumentConverter()
                result = converter.convert(str(file))
                return str(result.document.export_to_markdown())
            except Exception as exc:
                logger.warning("Docling docx conversion failed, falling back to python-docx", error=str(exc))
        document = Document(str(file))
        return "\n".join(p.text for p in document.paragraphs)
    if suffix == ".pdf":
        if DOCLING_AVAILABLE:
            try:
                converter = DocumentConverter()
                result = converter.convert(str(file))
                return str(result.document.export_to_markdown())
            except Exception as exc:
                logger.warning("Docling pdf conversion failed, falling back to pymupdf", error=str(exc))
        try:
            import fitz
        except ImportError as err:
            raise ImportError(
                "PDF support requires optional dependency: uv sync --extra pdf or pip install pymupdf"
            ) from err
        with fitz.open(str(file)) as doc:
            return "\n".join(page.get_text() for page in doc)
    raise ValueError("Unsupported resume format. Use .txt, .md, .docx, or install pdf extra.")


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    found = pattern.search(text)
    return found.group(0) if found else ""
