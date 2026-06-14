from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document

from linkedin_mcp_zero.storage.db import Storage
from linkedin_mcp_zero.utils.compress import clean_text, compact_dict, truncate

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
SKILLS = [
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
    "MCP",
    "Playwright",
]


class ResumeEngine:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def analyze_resume(self, path: str) -> dict[str, Any]:
        text = extract_resume_text(path)
        email = _first_match(EMAIL_RE, text)
        phone = _first_match(PHONE_RE, text)
        skills = [skill for skill in SKILLS if skill.lower() in text.lower()]
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

    def get_resume_insights(self, id: int) -> dict[str, Any]:
        resume = self.storage.get_resume(id)
        if not resume:
            return {"error": "resume_not_found", "id": id}
        skills = set(resume.get("skills", []))
        target = {"Python", "SQL", "AWS", "Docker", "Kubernetes", "FastAPI"}
        gaps = sorted(target - skills)
        strengths = sorted(skills & target)
        return {
            "id": id,
            "gap_skills": gaps[:8],
            "strengths": strengths[:8],
            "suggestions": [
                "Quantify impact with metrics",
                "Mirror target job keywords in the skills section",
                "Keep latest projects near the top",
            ],
            "market_pos": "Computed locally from resume keywords; LLM scoring can be added later.",
        }


def extract_resume_text(path: str) -> str:
    file = Path(path).expanduser()
    suffix = file.suffix.lower()
    if suffix in {".txt", ".md"}:
        return file.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        document = Document(str(file))
        return "\n".join(p.text for p in document.paragraphs)
    if suffix == ".pdf":
        try:
            import fitz  # type: ignore[import-not-found]
        except ImportError:
            return (
                "PDF support requires optional dependency: "
                "uv sync --extra pdf or pip install pymupdf"
            )
        with fitz.open(str(file)) as doc:
            return "\n".join(page.get_text() for page in doc)
    raise ValueError("Unsupported resume format. Use .txt, .md, .docx, or install pdf extra.")


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    found = pattern.search(text)
    return found.group(0) if found else ""
