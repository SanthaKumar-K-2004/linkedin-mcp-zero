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
        "Spring Boot",
        "Microservices",
        "REST",
    ],
    "frontend": [
        "JavaScript",
        "TypeScript",
        "React",
        "Next.js",
        "HTML",
        "CSS",
        "Tailwind",
        "TailwindCSS",
        "Redux",
        "GraphQL",
        "Vite",
        "Webpack",
        "UI/UX Design",
    ],
    "devops_cloud": [
        "AWS",
        "Docker",
        "Kubernetes",
        "Terraform",
        "CI/CD",
        "Linux",
        "Azure",
        "GCP",
        "Ansible",
        "Helm",
        "GitHub Actions",
        "Prometheus",
        "Grafana",
    ],
    "data_ai": [
        "Python",
        "SQL",
        "Machine Learning",
        "Deep Learning",
        "Pandas",
        "PyTorch",
        "TensorFlow",
        "Spark",
        "Airflow",
        "dbt",
        "NumPy",
        "LLM",
        "RAG",
    ],
    "mobile": [
        "Swift",
        "Kotlin",
        "React Native",
        "Flutter",
        "Dart",
        "iOS",
        "Android",
    ],
    "systems": [
        "Rust",
        "C++",
        "C",
        "Linux",
        "Unix",
        "eBPF",
        "gRPC",
        "Docker",
        "Cryptography",
    ],
    "product_management": [
        "Product Management",
        "Product Strategy",
        "Product Roadmapping",
        "Agile",
        "Scrum",
        "PRD",
        "User Stories",
        "Feature Prioritization",
        "OKRs",
        "KPI Tracking",
        "GTM Strategy",
        "A/B Testing",
        "Stakeholder Management",
        "Jira",
    ],
    "data_analytics_bi": [
        "Data Analytics",
        "Business Intelligence",
        "SQL",
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
        "Python",
    ],
    "marketing_growth": [
        "Digital Marketing",
        "SEO",
        "SEM",
        "Content Strategy",
        "Google Ads",
        "Meta Ads",
        "Email Marketing",
        "HubSpot",
        "Marketo",
        "Growth Hacking",
        "Customer Acquisition",
        "Lead Generation",
        "Brand Management",
        "A/B Testing",
    ],
    "sales_business_dev": [
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
    ],
    "finance_accounting": [
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
        "Financial Modeling",
    ],
    "operations_supply_chain": [
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
    ],
    "human_resources_talent": [
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
    ],
    "design_creative": [
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
    ],
    "customer_success_support": [
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
    ],
    "healthcare_clinical": [
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
        "BLS",
        "Case Management",
    ],
}

DOMAIN_ACTION_VERBS: dict[str, list[str]] = {
    "product_management": [
        "Spearheaded",
        "Prioritized",
        "Launched",
        "Orchestrated",
        "Defined",
        "Iterated",
        "Validated",
        "Aligned",
        "Benchmarked",
        "Scaled",
    ],
    "data_analytics_bi": [
        "Extracted",
        "Modeled",
        "Synthesized",
        "Visualized",
        "Automated",
        "Discovered",
        "Identified",
        "Correlated",
        "Forecasted",
        "Optimized",
    ],
    "marketing_growth": [
        "Generated",
        "Acquired",
        "Amplified",
        "Optimized",
        "Ranked",
        "Targeted",
        "Tested",
        "Converted",
        "Positioned",
        "Scaled",
    ],
    "sales_business_dev": [
        "Negotiated",
        "Closed",
        "Exceeded",
        "Prospected",
        "Expanded",
        "Generated",
        "Secured",
        "Outperformed",
        "Cultivated",
        "Captured",
    ],
    "finance_accounting": [
        "Audited",
        "Reconciled",
        "Forecasted",
        "Modeled",
        "Allocated",
        "Reduced",
        "Streamlined",
        "Ensured",
        "Analyzed",
        "Structured",
    ],
    "operations_supply_chain": [
        "Streamlined",
        "Procured",
        "Minimized",
        "Standardized",
        "Eliminated",
        "Negotiated",
        "Coordinated",
        "Restructured",
        "Implemented",
        "Enhanced",
    ],
    "human_resources_talent": [
        "Recruited",
        "Retained",
        "Onboarded",
        "Championed",
        "Facilitated",
        "Mediated",
        "Resolved",
        "Trained",
        "Administered",
        "Revamped",
    ],
    "design_creative": [
        "Conceptualized",
        "Prototyped",
        "Redesigned",
        "Conducted",
        "Iterated",
        "Crafted",
        "Unified",
        "Standardized",
        "Enhanced",
        "Architected",
    ],
    "customer_success_support": [
        "Retained",
        "Onboarded",
        "Advocated",
        "Resolved",
        "Decreased",
        "Boosted",
        "Managed",
        "Cultivated",
        "De-escalated",
        "Maximized",
    ],
    "healthcare_clinical": [
        "Administered",
        "Triaged",
        "Monitored",
        "Coordinated",
        "Documented",
        "Assessed",
        "Collaborated",
        "Educated",
        "Ensured",
        "Delivered",
    ],
    "backend": [
        "Architected",
        "Engineered",
        "Refactored",
        "Optimized",
        "Deployed",
        "Automated",
        "Decoupled",
        "Scaled",
        "Integrated",
        "Implemented",
    ],
    "frontend": [
        "Engineered",
        "Implemented",
        "Redesigned",
        "Optimized",
        "Integrated",
        "Built",
        "Enhanced",
        "Architected",
        "Delivered",
        "Refactored",
    ],
    "devops_cloud": [
        "Automated",
        "Provisioned",
        "Containerized",
        "Migrated",
        "Hardened",
        "Monitored",
        "Orchestrated",
        "Configured",
        "Standardized",
        "Scaled",
    ],
    "data_ai": [
        "Trained",
        "Fine-tuned",
        "Engineered",
        "Deployed",
        "Extracted",
        "Evaluated",
        "Benchmarked",
        "Modeled",
        "Optimized",
        "Constructed",
    ],
    "mobile": [
        "Developed",
        "Engineered",
        "Published",
        "Optimized",
        "Refactored",
        "Integrated",
        "Shipped",
        "Architected",
        "Tested",
        "Designed",
    ],
    "systems": [
        "Engineered",
        "Optimized",
        "Benchmarked",
        "Hardened",
        "Implemented",
        "Debugged",
        "Compiled",
        "Profiled",
        "Refactored",
        "Architected",
    ],
}

DOMAIN_HEADINGS: dict[str, str] = {
    "healthcare_clinical": "CLINICAL SKILLS & CERTIFICATIONS",
    "design_creative": "DESIGN TOOLING & METHODOLOGIES",
    "finance_accounting": "FINANCIAL COMPETENCIES & SYSTEMS",
    "sales_business_dev": "SALES COMPETENCIES & CRM SYSTEMS",
    "marketing_growth": "MARKETING TOOLING & GROWTH COMPETENCIES",
    "product_management": "PRODUCT & AGILE COMPETENCIES",
    "operations_supply_chain": "OPERATIONAL COMPETENCIES & ERP",
    "human_resources_talent": "HR COMPETENCIES & HRIS SYSTEMS",
    "data_analytics_bi": "ANALYTICS, BI & DATA TOOLING",
}

DOMAIN_SAMPLE_BULLETS: dict[str, str] = {
    "product_management": (
        "Spearheaded end-to-end launch of self-serve onboarding flow, increasing 30-day user retention "
        "by 24% and unlocking $1.8M ARR, by synthesizing 50+ customer discovery interviews and prioritizing MVP features across 4 agile sprints."
    ),
    "data_analytics_bi": (
        "Automated enterprise revenue and churn dashboard in Tableau and SQL, cutting weekly executive reporting lag "
        "from 4 days to real-time and identifying $320K in cost anomalies, by engineering modular BigQuery ETL pipelines."
    ),
    "marketing_growth": (
        "Scaled organic customer acquisition by 165% and lowered blended CAC by 28%, generating $2.4M in pipeline revenue, "
        "by executing comprehensive technical SEO audit, high-intent content clusters, and automated HubSpot nurturing workflows."
    ),
    "sales_business_dev": (
        "Closed $3.1M in new ARR across 14 enterprise accounts at 142% of annual quota, reducing average sales cycle "
        "from 90 to 52 days, by executing consultative multi-threaded outreach and executive business reviews via Salesforce CRM."
    ),
    "finance_accounting": (
        "Streamlined annual budgeting and month-end close procedures, reducing reporting variance from 12% to under 2.5% "
        "and accelerating close cycle by 4 days, by building driver-based rolling financial forecasts in NetSuite and Excel."
    ),
    "operations_supply_chain": (
        "Restructured regional distribution logistics and vendor contracts, reducing order fulfillment cycle time by 32% "
        "and saving $580K annually, by deploying Lean Six Sigma continuous improvement protocols and consolidating 8 supplier contracts."
    ),
    "human_resources_talent": (
        "Orchestrated full-cycle talent acquisition across 45 strategic hires, slashing average time-to-hire from 58 to 27 days "
        "while maintaining a 96% 1-year retention rate, by designing structured behavioral interview rubrics and optimizing Greenhouse ATS pipelines."
    ),
    "design_creative": (
        "Redesigned multi-platform checkout experience in Figma, lifting mobile conversion rates by 19% and decreasing checkout abandonment "
        "by 35%, by conducting 5 rounds of moderated usability testing and architecting an accessible cross-platform design system."
    ),
    "customer_success_support": (
        "Maintained 118% Net Revenue Retention (NRR) and 97% CSAT across a $4.2M enterprise account portfolio, reducing customer churn by 40%, "
        "by instituting automated account health-score triggers in Zendesk and quarterly strategic business reviews."
    ),
    "healthcare_clinical": (
        "Triaged and coordinated comprehensive care plans for 25+ high-acuity patients per shift, reducing intake wait times by 26% "
        "and maintaining 99.8% medication administration accuracy, by standardizing clinical documentation workflows in Epic Systems EHR."
    ),
    "backend": (
        "Architected distributed event-driven payment processing microservices handling 12,000 req/sec at zero transaction loss, "
        "reducing p99 API latency by 45%, by migrating synchronous REST bottlenecks to Kafka worker pools in Go and PostgreSQL."
    ),
    "frontend": (
        "Engineered real-time collaboration canvas in React and TypeScript, boosting interactive frame rates from 24 to 60 FPS "
        "and reducing initial bundle load by 42%, by implementing virtualized windowing and WebGL rendering optimizations."
    ),
    "devops_cloud": (
        "Automated multi-region cloud infrastructure migration across 80+ microservices, lowering monthly AWS infrastructure spend by 35% "
        "and achieving 99.99% uptime, by authoring modular Terraform configurations and Kubernetes GitOps pipelines in ArgoCD."
    ),
    "data_ai": (
        "Engineered high-throughput RAG search pipeline indexing 2M+ unstructured documents, increasing retrieval accuracy by 34% "
        "and reducing query latency by 60%, by fine-tuning embedding models and deploying Qdrant vector search on Kubernetes."
    ),
    "mobile": (
        "Developed and published native mobile application with 200K+ monthly active users, achieving a 4.9-star App Store rating "
        "and 99.9% crash-free sessions, by refactoring state management to Swift Concurrency and optimizing offline SQLite caching."
    ),
    "systems": (
        "Engineered low-latency kernel network packet filter in C and eBPF, reducing packet drop rates by 88% under 40Gbps DDoS load, "
        "by eliminating user-space memory copies and optimizing lock-free ring buffers in Linux."
    ),
}

ROLE_DOMAIN_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        "healthcare_clinical",
        [
            "nurse",
            "nursing",
            "clinical",
            "patient",
            "medical",
            "physician",
            "doctor",
            "hospital",
            "phlebotom",
            "healthcare",
            "clinic",
            "bls",
            "ehr",
            "epic",
        ],
    ),
    (
        "product_management",
        [
            "product manager",
            "product lead",
            "product owner",
            "head of product",
            "vp of product",
            "technical product",
            "scrum master",
            "agile coach",
            "prd",
        ],
    ),
    (
        "data_analytics_bi",
        [
            "data analyst",
            "business intelligence",
            "bi analyst",
            "analytics manager",
            "power bi",
            "tableau",
            "looker",
            "reporting analyst",
            "data visualization",
        ],
    ),
    (
        "data_ai",
        [
            "machine learning",
            "ml engineer",
            "data scientist",
            "ai engineer",
            "deep learning",
            "nlp",
            "computer vision",
            "llm",
            "rag",
            "pytorch",
            "tensorflow",
        ],
    ),
    (
        "marketing_growth",
        [
            "marketing",
            "growth",
            "seo",
            "sem",
            "content strategist",
            "copywriter",
            "social media",
            "brand manager",
            "demand gen",
            "hubspot",
        ],
    ),
    (
        "sales_business_dev",
        [
            "sales",
            "account executive",
            "business development",
            "bdr",
            "sdr",
            "sales manager",
            "commercial",
            "enterprise sales",
            "salesforce",
        ],
    ),
    (
        "finance_accounting",
        [
            "accountant",
            "accounting",
            "financial analyst",
            "controller",
            "cfo",
            "finance manager",
            "audit",
            "treasury",
            "bookkeeper",
            "gaap",
            "ifrs",
            "netsuite",
        ],
    ),
    (
        "operations_supply_chain",
        [
            "supply chain",
            "logistics",
            "procurement",
            "operations manager",
            "warehouse",
            "inventory",
            "lean",
            "six sigma",
            "fulfillment",
        ],
    ),
    (
        "human_resources_talent",
        [
            "human resources",
            "recruiter",
            "talent acquisition",
            "hr generalist",
            "hr manager",
            "people ops",
            "people operations",
            "workday",
            "hris",
        ],
    ),
    (
        "design_creative",
        [
            "ui/ux",
            "product designer",
            "ux designer",
            "graphic designer",
            "visual designer",
            "interaction designer",
            "art director",
            "figma",
        ],
    ),
    (
        "customer_success_support",
        [
            "customer success",
            "client success",
            "customer support",
            "support specialist",
            "client manager",
            "account coordinator",
            "zendesk",
            "csat",
        ],
    ),
    (
        "devops_cloud",
        [
            "devops",
            "cloud engineer",
            "sre",
            "site reliability",
            "infrastructure",
            "platform engineer",
            "sysadmin",
            "terraform",
            "kubernetes",
        ],
    ),
    (
        "mobile",
        [
            "ios",
            "android",
            "flutter",
            "react native",
            "mobile developer",
            "swift",
            "kotlin",
        ],
    ),
    (
        "systems",
        [
            "systems engineer",
            "embedded",
            "firmware",
            "c++",
            "rust developer",
            "kernel",
            "ebpf",
        ],
    ),
    (
        "frontend",
        [
            "frontend",
            "front-end",
            "ui developer",
            "react developer",
            "web developer",
            "javascript developer",
        ],
    ),
    (
        "backend",
        [
            "backend",
            "back-end",
            "python developer",
            "java developer",
            "go developer",
            "api developer",
            "software engineer",
            "software developer",
        ],
    ),
]


def _infer_domain_name(skills: list[str], target_role: str = "", text: str = "") -> str:
    combined_target = f"{target_role} {text}".lower()
    for domain, kws in ROLE_DOMAIN_KEYWORDS:
        if any(kw in combined_target for kw in kws):
            return domain

    sk_lower = {s.lower() for s in skills}
    best_domain = "backend"
    best_score = 0
    for domain, domain_skills in DOMAIN_ECOSYSTEMS.items():
        overlap = sum(1 for s in domain_skills if s.lower() in sk_lower)
        if overlap > best_score:
            best_score = overlap
            best_domain = domain
    return best_domain


def _infer_domain_ecosystem(skills: list[str]) -> set[str]:
    domain = _infer_domain_name(skills)
    return set(DOMAIN_ECOSYSTEMS.get(domain, DOMAIN_ECOSYSTEMS["backend"]))


MAX_RESUME_BYTES = 10 * 1024 * 1024


def _get_allowed_resume_dirs(settings: Any) -> list[Path]:
    if settings.allowed_resume_dirs:
        return [Path(d).expanduser().resolve() for d in settings.allowed_resume_dirs]
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
    return allowed


def extract_job_id_from_input(val: str) -> str | None:
    cleaned = val.strip()
    if cleaned.isdigit() and len(cleaned) >= 6:
        return cleaned
    m = re.search(r"/(?:jobs/view/|view/)(\d+)", cleaned)
    if m:
        return m.group(1)
    m = re.search(r"(?:currentJobId=|jobId=)(\d+)", cleaned)
    if m:
        return m.group(1)
    return None


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
        allowed = _get_allowed_resume_dirs(settings)
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
        expanded_skills_map = self.storage.expand_skills(candidate_skills, include_curated=True)
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

    async def tailor_resume(
        self,
        path: str,
        target_job: str = "",
        target_role: str = "",
        ctx: Any | None = None,
    ) -> dict[str, Any]:
        settings = self.storage.settings
        allowed = _get_allowed_resume_dirs(settings)
        text = extract_resume_text(path, allowed_dirs=allowed)

        candidate_skills = extract_skills_from_text(text, SKILLS)
        candidate_skill_set = {s.lower() for s in candidate_skills}
        email = _first_match(EMAIL_RE, text)
        phone = _first_match(PHONE_RE, text)
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        name = lines[0] if lines else "Candidate"

        job_text = ""
        job_metadata: dict[str, Any] = {}

        if target_job:
            extracted_id = extract_job_id_from_input(target_job)
            if extracted_id and self.public is not None:
                try:
                    job_data = await self.public.get_job_details(extracted_id)
                    if isinstance(job_data, dict) and not job_data.get("error"):
                        job_metadata = job_data
                        job_text = f"{job_data.get('t', '')} {job_data.get('co', '')} {job_data.get('desc', '')}"
                        if not target_role and job_data.get("t"):
                            target_role = str(job_data["t"])
                except Exception as exc:
                    logger.warning("Failed to fetch live job details for resume tailoring", error=str(exc))
            if not job_text:
                job_text = target_job

        if not job_text and target_role and self.public is not None:
            try:
                live_jobs = await self.public.search_jobs(kw=target_role, limit=10)
                job_text = " ".join(f"{j.get('t', '')} {j.get('co', '')} {j.get('desc', '')}" for j in live_jobs)
            except Exception as exc:
                logger.warning("Failed to search market jobs for target role", role=target_role, error=str(exc))

        domain = _infer_domain_name(candidate_skills, target_role=target_role, text=f"{text} {job_text}")
        ecosystem_skills = DOMAIN_ECOSYSTEMS.get(domain, DOMAIN_ECOSYSTEMS["backend"])
        action_verbs = DOMAIN_ACTION_VERBS.get(domain, DOMAIN_ACTION_VERBS["backend"])
        skills_heading = DOMAIN_HEADINGS.get(domain, "TECHNICAL SKILLS")
        sample_bullet = DOMAIN_SAMPLE_BULLETS.get(domain, DOMAIN_SAMPLE_BULLETS["backend"])

        if job_text:
            extracted_target = extract_skills_from_text(job_text, SKILLS)
            target_skills = extracted_target if extracted_target else ecosystem_skills[:12]
        else:
            target_skills = ecosystem_skills[:12]

        present_skills = [s for s in target_skills if s.lower() in candidate_skill_set]
        missing_skills = [s for s in target_skills if s.lower() not in candidate_skill_set]
        total_target = max(len(target_skills), 1)
        ats_score = min(100, round((len(present_skills) / total_target) * 100))

        if ats_score >= 70:
            match_status = "High Alignment"
        elif ats_score >= 40:
            match_status = "Moderate Alignment"
        else:
            match_status = "Needs Optimization"

        display_role = target_role or domain.replace("_", " ").title()

        tailored_summary = (
            f"Results-driven {display_role} with proven track record in {', '.join(present_skills[:4]) if present_skills else 'core competencies'}. "
            f"Specialized in driving measurable organizational impact, cross-functional collaboration, and high-performance execution. "
            f"Experienced in leveraging {', '.join(ecosystem_skills[:3])} to deliver high-quality outcomes."
        )

        actionable_steps = [
            f"Add or rename the top skills section to '## {skills_heading}' and list validated competencies directly under contact info.",
            f"Prioritize incorporating top missing keywords where you have genuine experience: {', '.join(missing_skills[:5]) if missing_skills else 'All core target skills present'}.",
            f"Rephrase experience bullet points using high-impact domain action verbs: {', '.join(action_verbs[:6])}.",
            "Format all accomplishments strictly via the Google XYZ formula: 'Accomplished [X] as measured by [Y], by doing [Z]'.",
            "Maintain a strictly linear, single-column layout with standard markdown/text to ensure 100% ATS parser compatibility.",
        ]

        result: dict[str, Any] = {
            "path": path,
            "candidate_name": name,
            "email": email,
            "phone": phone,
            "identified_domain": domain,
            "domain_display": domain.replace("_", " ").title(),
            "target_role": display_role,
            "ats_compatibility_score": ats_score,
            "match_status": match_status,
            "skills_analysis": {
                "candidate_total_skills": len(candidate_skills),
                "target_required_skills": len(target_skills),
                "matching_skills": present_skills,
                "missing_skills": missing_skills,
            },
            "ats_layout_guidance": {
                "recommended_skills_heading": skills_heading,
                "domain_action_verbs": action_verbs[:10],
                "actionable_tailoring_steps": actionable_steps,
            },
            "accomplishment_formula": {
                "benchmark": "Accomplished [X] as measured by [Y], by doing [Z]",
                "domain_sample_bullet": sample_bullet,
            },
            "tailored_summary_suggestion": tailored_summary,
        }

        if job_metadata:
            result["target_job_info"] = {
                "title": job_metadata.get("t", ""),
                "company": job_metadata.get("co", ""),
                "location": job_metadata.get("loc", ""),
                "url": job_metadata.get("url", ""),
            }

        if ctx is not None or self.llm_provider.api_key or self.llm_provider.openai_api_key:
            prompt = f"""Tailor this candidate's resume for the target job with strict ATS compliance:
Candidate Name: {name}
Target Role / Job: {display_role}
Domain: {domain}
Current Skills: {", ".join(candidate_skills)}
Matching Skills: {", ".join(present_skills)}
Missing Target Keywords: {", ".join(missing_skills)}
Original Resume Excerpt:
{truncate(text, 1200)}

Requirements:
1. Provide an optimized ATS Professional Summary (3-4 sentences, incorporating relevant keywords naturally).
2. Rewrite 3 bullet points applying the Google XYZ formula ("Accomplished [X] as measured by [Y], by doing [Z]") using domain-appropriate action verbs.
3. NEVER fabricate experience, employers, or false metrics. Rephrase and elevate real accomplishments."""
            try:
                ai_tailoring = await self.llm_provider.generate(
                    prompt=prompt,
                    system_prompt=f"You are a Principal Talent Acquisition Partner specializing in {display_role} recruitment. Write crisp, metric-driven, ATS-tailored content.",
                    ctx=ctx,
                )
                result["llm_tailored_suggestions"] = ai_tailoring
            except Exception as e:
                logger.warning("LLM resume tailoring generation failed, returning algorithmic tailoring", error=str(e))

        return result


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
    # Defense in depth inside the allowed folders: no dotfiles/dot-directories (.ssh, .env, .config ...)
    # and no oversized files (zip-bomb / memory exhaustion).
    if any(part.startswith(".") and part not in {".", ".."} for part in file.parts[1:]):
        raise ValueError("Resume path may not point to hidden files or folders")
    if file.stat().st_size > MAX_RESUME_BYTES:
        raise ValueError(f"Resume file too large (limit {MAX_RESUME_BYTES // (1024 * 1024)} MB)")

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
