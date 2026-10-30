from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache
from typing import Any

from linkedin_mcp_zero.config.skill_taxonomy import (
    ALIAS_TO_CANON,
    AMBIGUOUS,
    SEED_EDGES,
    TAXONOMY,
)

_LEGACY_SKILLS: list[str] = [
    # Core Languages
    "Python",
    "JavaScript",
    "TypeScript",
    "Go",
    "Golang",
    "Rust",
    "Java",
    "C++",
    "C#",
    "C",
    "Ruby",
    "PHP",
    "Swift",
    "Kotlin",
    "Scala",
    "R",
    "Dart",
    "Elixir",
    "Julia",
    "Shell",
    "Bash",
    "SQL",
    "HTML",
    "CSS",
    # Frontend & UI
    "React",
    "React Native",
    "Vue",
    "Vue.js",
    "Angular",
    "Svelte",
    "Next.js",
    "Nuxt",
    "Remix",
    "Tailwind",
    "TailwindCSS",
    "Redux",
    "Vite",
    "Webpack",
    "GraphQL",
    "REST",
    "WebSockets",
    # Backend & Web Frameworks
    "Node.js",
    "Node",
    "Express",
    "FastAPI",
    "Django",
    "Flask",
    "Spring Boot",
    "Spring",
    "ASP.NET",
    ".NET",
    "Ruby on Rails",
    "Rails",
    "NestJS",
    "Gin",
    "Actix",
    "Axum",
    "gRPC",
    # Cloud & Infrastructure
    "AWS",
    "Azure",
    "GCP",
    "Google Cloud",
    "Terraform",
    "Ansible",
    "Pulumi",
    "CloudFormation",
    "OpenStack",
    "Serverless",
    "Lambda",
    # Containers & Orchestration
    "Docker",
    "Kubernetes",
    "Helm",
    "OpenShift",
    "Nomad",
    # CI/CD & DevOps
    "Jenkins",
    "GitHub Actions",
    "GitLab CI",
    "ArgoCD",
    "CircleCI",
    "Tekton",
    "Prometheus",
    "Grafana",
    "Datadog",
    # Databases & Storage
    "PostgreSQL",
    "Postgres",
    "MySQL",
    "MariaDB",
    "SQLite",
    "MongoDB",
    "Cassandra",
    "DynamoDB",
    "Redis",
    "Elasticsearch",
    "OpenSearch",
    "Neo4j",
    "Qdrant",
    "Pinecone",
    "Milvus",
    "Chroma",
    "Snowflake",
    "BigQuery",
    "ClickHouse",
    # Messaging & Distributed Systems
    "Apache Kafka",
    "Kafka",
    "RabbitMQ",
    "Celery",
    "NATS",
    "Pulsar",
    "SQS",
    # AI / Machine Learning / Data
    "Machine Learning",
    "Deep Learning",
    "AI",
    "LLM",
    "NLP",
    "Computer Vision",
    "PyTorch",
    "TensorFlow",
    "Keras",
    "scikit-learn",
    "Pandas",
    "NumPy",
    "Polars",
    "Spark",
    "PySpark",
    "Airflow",
    "dbt",
    "Hugging Face",
    "LangChain",
    "LlamaIndex",
    "MCP",
    "RAG",
    # Systems, Security & Testing
    "Linux",
    "Unix",
    "eBPF",
    "OAuth",
    "JWT",
    "OWASP",
    "Cryptography",
    "Playwright",
    "Selenium",
    "Cypress",
    "Pytest",
    "Jest",
    # Product Management & Agile
    "Product Management",
    "Product Strategy",
    "Product Roadmapping",
    "Agile",
    "Scrum",
    "Kanban",
    "PRD",
    "User Stories",
    "Feature Prioritization",
    "Wireframing",
    "OKRs",
    "KPI Tracking",
    "GTM Strategy",
    "A/B Testing",
    "Stakeholder Management",
    "Market Research",
    "Competitive Analysis",
    "Jira",
    "Confluence",
    # Data Analytics & Business Intelligence
    "Data Analytics",
    "Business Intelligence",
    "Tableau",
    "Power BI",
    "Looker",
    "Excel",
    "Financial Modeling",
    "Google Analytics",
    "Statistics",
    "Data Visualization",
    "ETL",
    "Metric Reporting",
    "Business Analysis",
    "Predictive Analytics",
    # Marketing, Growth & Brand
    "Digital Marketing",
    "SEO",
    "SEM",
    "Content Strategy",
    "Copywriting",
    "Google Ads",
    "Meta Ads",
    "Email Marketing",
    "HubSpot",
    "Marketo",
    "Social Media Marketing",
    "Growth Hacking",
    "Customer Acquisition",
    "Lead Generation",
    "Brand Management",
    "Conversion Rate Optimization",
    # Sales & Business Development
    "Salesforce",
    "CRM",
    "B2B Sales",
    "Enterprise Sales",
    "Cold Outreach",
    "Pipeline Management",
    "Quota Attainment",
    "Account Management",
    "Solution Selling",
    "Contract Negotiation",
    "Revenue Operations",
    "Business Development",
    "Territory Management",
    # Finance, Accounting & Banking
    "Financial Analysis",
    "US GAAP",
    "IFRS",
    "Budgeting",
    "Forecasting",
    "P&L Management",
    "Audit",
    "Tax Compliance",
    "QuickBooks",
    "NetSuite",
    "SAP",
    "Cash Flow Management",
    "Variance Analysis",
    "Internal Controls",
    "Risk Management",
    # Operations & Supply Chain
    "Supply Chain Management",
    "Logistics",
    "Procurement",
    "Vendor Management",
    "Lean Six Sigma",
    "Six Sigma",
    "Inventory Control",
    "Process Optimization",
    "ERP",
    "Continuous Improvement",
    "Quality Assurance",
    "Root Cause Analysis",
    "Kaizen",
    "Warehouse Management",
    # Human Resources & Talent Acquisition
    "Human Resources",
    "Talent Acquisition",
    "Full-Cycle Recruiting",
    "Employee Relations",
    "HRIS",
    "Workday",
    "Performance Management",
    "Onboarding",
    "HR Compliance",
    "Organizational Development",
    "HR Policies",
    "DE&I",
    "Employee Engagement",
    "Benefits Administration",
    # Design, UI/UX & Creative
    "UI/UX Design",
    "Product Design",
    "Figma",
    "User Research",
    "Prototyping",
    "Usability Testing",
    "Adobe Creative Cloud",
    "Design Systems",
    "Information Architecture",
    "Interaction Design",
    "Visual Design",
    # Customer Success & Support
    "Customer Success",
    "Customer Retention",
    "Churn Reduction",
    "Zendesk",
    "ServiceNow",
    "CSAT",
    "NPS",
    "Client Onboarding",
    "Escalation Management",
    "Account Health",
    # Healthcare & Clinical
    "Patient Care",
    "Clinical Research",
    "Electronic Health Records",
    "EHR",
    "Epic Systems",
    "Cerner",
    "HIPAA Compliance",
    "HIPAA",
    "Triage",
    "Phlebotomy",
    "Medical Billing",
    "Patient Assessment",
    "Patient Education",
    "BLS",
    "Infection Control",
    "Case Management",
]


_known = {s.lower() for s in _LEGACY_SKILLS}
COMMON_SKILLS: list[str] = _LEGACY_SKILLS + [name for name in TAXONOMY if name.lower() not in _known]

# Legacy names that are really aliases of a canonical taxonomy skill.
for _legacy in _LEGACY_SKILLS:
    ALIAS_TO_CANON.setdefault(_legacy.lower(), _legacy)

_AMBIGUOUS_LOWER = {a.lower() for a in AMBIGUOUS}
_DELIMS = set(",;/|:()[]\u2022\u00b7-\u2013\n\t")
_BEFORE = r"(?<![A-Za-z0-9_+#])"
_AFTER = r"(?![A-Za-z0-9_+#])"


def canonicalize_skill(skill: str) -> str:
    """Map any alias/spelling (k8s, postgres, golang, google cloud) to its canonical skill name."""
    key = re.sub(r"\s+", " ", (skill or "").strip()).lower()
    return ALIAS_TO_CANON.get(key, (skill or "").strip())


def skill_category(skill: str) -> str:
    info = TAXONOMY.get(canonicalize_skill(skill))
    return str(info["category"]) if info else "general"


@lru_cache(maxsize=4)
def _compile(terms: tuple[str, ...]) -> re.Pattern[str]:
    ordered = sorted(terms, key=len, reverse=True)
    body = "|".join(re.escape(t) for t in ordered)
    return re.compile(f"{_BEFORE}(?P<t>{body}){_AFTER}", re.IGNORECASE)


def _context_ok(text: str, start: int, end: int) -> bool:
    left = text[:start].rstrip(" ")
    right = text[end:].lstrip(" ")
    before = left[-1:] if left else "\n"
    after = right[:1] if right else "\n"
    return before in _DELIMS or after in _DELIMS


def extract_skills_from_text(text: str, skills: list[str] | None = None) -> list[str]:
    """Extract canonical skills in order of first appearance.

    Uses one compiled regex (fast), resolves aliases (k8s -> Kubernetes), and guards ambiguous
    short terms (C, R, Go, AI ...) so ordinary words do not become skills.
    """
    if not text:
        return []
    custom = skills is not None and skills is not COMMON_SKILLS
    if custom:
        mapping = {s.lower(): s for s in (skills or [])}
    else:
        mapping = {**{n.lower(): n for n in COMMON_SKILLS}, **ALIAS_TO_CANON}
    if not mapping:
        return []
    pattern = _compile(tuple(sorted(mapping)))

    found: list[str] = []
    seen: set[str] = set()
    deferred: list[tuple[str, str]] = []
    for match in pattern.finditer(text):
        raw = match.group("t")
        low = raw.lower()
        canon = mapping[low]
        if not custom and low in _AMBIGUOUS_LOWER:
            exact_ok = raw in AMBIGUOUS or raw == canon
            if not exact_ok:
                continue
            if not _context_ok(text, match.start(), match.end()):
                deferred.append((canon, raw))
                continue
        if canon.lower() not in seen:
            seen.add(canon.lower())
            found.append(canon)

    # Ambiguous terms without list-style context count only if a same-category skill corroborates them.
    cats = {skill_category(f) for f in found}
    for canon, _raw in deferred:
        if canon.lower() not in seen and skill_category(canon) in cats and skill_category(canon) != "general":
            seen.add(canon.lower())
            found.append(canon)
    return found


def seed_relations() -> list[tuple[str, str, str, float]]:
    """(source, target, relation, weight) edges from the taxonomy, mirrored both ways."""
    edges: dict[tuple[str, str], float] = {}
    for a, b in SEED_EDGES:
        ca, cb = canonicalize_skill(a).lower(), canonicalize_skill(b).lower()
        if ca and cb and ca != cb:
            edges[(ca, cb)] = 3.0
            edges[(cb, ca)] = 3.0
    return [(a, b, "related_to", w) for (a, b), w in edges.items()]


def skill_gap(candidate: list[str], required: list[str], related: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Compare candidate vs required skills with alias + adjacency credit.

    matched     - same canonical skill
    transferable- missing, but candidate has a closely related skill (fast to learn)
    missing     - nothing close on the resume
    """
    cand = {canonicalize_skill(s).lower(): canonicalize_skill(s) for s in candidate if s}
    req = list(dict.fromkeys(canonicalize_skill(s) for s in required if s))
    neighbors: dict[str, set[str]] = defaultdict(set)
    for src, targets in (related or {}).items():
        for t in targets:
            neighbors[canonicalize_skill(src).lower()].add(canonicalize_skill(t).lower())
            neighbors[canonicalize_skill(t).lower()].add(canonicalize_skill(src).lower())
    matched: list[str] = []
    transferable: list[dict[str, str]] = []
    missing: list[str] = []
    for r in req:
        key = r.lower()
        if key in cand:
            matched.append(r)
            continue
        close = next((cand[n] for n in neighbors.get(key, ()) if n in cand), None)
        if close:
            transferable.append({"need": r, "have": close})
        else:
            missing.append(r)
    score = (len(matched) + 0.5 * len(transferable)) / len(req) if req else 0.0
    return {
        "score": round(score, 2),
        "matched": matched,
        "transferable": transferable,
        "missing": missing,
    }


@lru_cache(maxsize=1)
def _curated_graph() -> dict[str, dict[str, float]]:
    graph: dict[str, dict[str, float]] = defaultdict(dict)
    for a, b, _rel, w in seed_relations():
        graph[a][b] = w
    return graph


def curated_neighbors(skill: str) -> dict[str, float]:
    """Taxonomy relations for a skill (alias-aware), as {display_name: weight}. Works with zero learned data."""
    graph = _curated_graph()
    out: dict[str, float] = {}
    for key in alias_keys(skill):
        for neighbor, weight in graph.get(key, {}).items():
            out[_display(neighbor)] = max(out.get(_display(neighbor), 0.0), weight)
    return out


def _display(lower_name: str) -> str:
    return ALIAS_TO_CANON.get(lower_name, lower_name)


def alias_keys(skill: str) -> set[str]:
    """All lowercase spellings of a skill: itself, its canonical name and every known alias."""
    low = (skill or "").strip().lower()
    canon = canonicalize_skill(skill)
    keys = {low, canon.lower()}
    info = TAXONOMY.get(canon)
    if info:
        keys.update(str(a).lower() for a in info["aliases"])  # type: ignore[attr-defined]
    return {k for k in keys if k}
