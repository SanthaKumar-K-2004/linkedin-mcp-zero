from __future__ import annotations

import re

# Canonical skill dictionary shared by resume parsing, job detail extraction,
# and job/resume matching. Long/most-specific terms first so multi-word skills
# are matched as a unit.
SKILLS: list[str] = [
    "Machine Learning",
    "Data Science",
    "Deep Learning",
    "Artificial Intelligence",
    "Natural Language Processing",
    "Computer Vision",
    "Node.js",
    "Next.js",
    "Vue.js",
    "TypeScript",
    "JavaScript",
    "React",
    "Angular",
    "Express",
    "Django",
    "FastAPI",
    "Flask",
    "Spring",
    "Python",
    "Java",
    "Kotlin",
    "Scala",
    "Golang",
    "Rust",
    "C++",
    "C#",
    ".NET",
    "PHP",
    "Ruby",
    "Swift",
    "MATLAB",
    "R",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "SQLite",
    "MongoDB",
    "Redis",
    "Elasticsearch",
    "Kafka",
    "Spark",
    "Hadoop",
    "Airflow",
    "Snowflake",
    "Databricks",
    "dbt",
    "Tableau",
    "Power BI",
    "Excel",
    "Pandas",
    "NumPy",
    "TensorFlow",
    "PyTorch",
    "scikit-learn",
    "AWS",
    "Azure",
    "GCP",
    "Docker",
    "Kubernetes",
    "Terraform",
    "Ansible",
    "Jenkins",
    "GitLab CI",
    "GitHub Actions",
    "CI/CD",
    "DevOps",
    "Linux",
    "Bash",
    "Git",
    "GraphQL",
    "REST",
    "gRPC",
    "Microservices",
    "Serverless",
    "LLM",
    "RAG",
    "MCP",
    "Playwright",
    "Selenium",
    "Agile",
    "Scrum",
    "OAuth",
    "AI",
]

# Skills that must match case-sensitively to avoid false positives
# (e.g. "AI" must not match the "ai" inside "maintain"/"email").
_CASE_SENSITIVE = {"AI", "R"}

# Skills whose names contain regex-hostile characters still work because we
# re.escape() every term; word boundaries are only applied around \w edges.
_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _pattern_for(skill: str) -> re.Pattern[str]:
    pattern = _PATTERN_CACHE.get(skill)
    if pattern is None:
        escaped = re.escape(skill)
        # (?<!\w) / (?!\w) act as boundaries that also work for terms ending
        # or starting with punctuation (C++, C#, .NET, Node.js).
        body = rf"(?<!\w){escaped}(?!\w)"
        flags = 0 if skill in _CASE_SENSITIVE else re.IGNORECASE
        pattern = re.compile(body, flags)
        _PATTERN_CACHE[skill] = pattern
    return pattern


def match_skills(text: str, known: list[str] | None = None) -> list[str]:
    """Return canonical skills present in text using boundary-aware matching.

    Unlike naive ``substring in text`` checks this does not report "AI" for a
    job description containing "detail-oriented" or "email", and still matches
    "AI/ML", "Node.js", or "C++" correctly.
    """
    if not text:
        return []
    candidates = known if known is not None else SKILLS
    return [skill for skill in candidates if _pattern_for(skill).search(text)]
