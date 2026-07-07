from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from platformdirs import user_data_dir

from linkedin_mcp_zero.config.defaults import DATA_DIR_NAME
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
        settings = self.storage.settings
        allowed = []
        if settings.allowed_resume_dirs:
            allowed = [Path(d).expanduser().resolve() for d in settings.allowed_resume_dirs]
        else:
            allowed = [
                Path.home() / "Documents",
                Path.home() / "Downloads",
                Path("/tmp"),
            ]
            if settings.data_dir:
                allowed.append(Path(settings.data_dir).expanduser().resolve())
            else:
                allowed.append(Path(user_data_dir(DATA_DIR_NAME)).expanduser().resolve())
            allowed.append(Path.cwd().resolve())

        text = extract_resume_text(path, allowed_dirs=allowed)
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


def extract_resume_text(path: str, allowed_dirs: list[Path] | None = None) -> str:
    file = Path(path).expanduser().resolve()

    if allowed_dirs is None:
        allowed_dirs = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path("/tmp"),
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
