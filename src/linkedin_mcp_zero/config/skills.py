from __future__ import annotations

import re

COMMON_SKILLS: list[str] = [
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


def extract_skills_from_text(text: str, skills: list[str] | None = None) -> list[str]:
    """Extract recognized technical skills using word-boundary regex matching."""
    target_skills = skills or COMMON_SKILLS
    return [skill for skill in target_skills if re.search(rf"\b{re.escape(skill)}\b", text, re.IGNORECASE)]
