from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any, Literal, cast

import structlog
from fastmcp import Context, FastMCP
from pydantic import BaseModel

from linkedin_mcp_zero.config.autodetect import detect_runtime
from linkedin_mcp_zero.config.defaults import DEFAULT_LIMIT
from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.engines.browser import BrowserEngine
from linkedin_mcp_zero.engines.matching import MatchingEngine
from linkedin_mcp_zero.engines.multi_board import search_jobs_multi as multi_search
from linkedin_mcp_zero.engines.public_api import PublicAPIEngine
from linkedin_mcp_zero.engines.resume import ResumeEngine
from linkedin_mcp_zero.engines.voyager import VoyagerEngine
from linkedin_mcp_zero.metrics.store import MetricsStore
from linkedin_mcp_zero.metrics.tracking import track_async_tool, track_sync_tool
from linkedin_mcp_zero.server.catalog import TOOLS, tool_help
from linkedin_mcp_zero.storage.db import Storage
from linkedin_mcp_zero.utils.llm import LLMProvider
from linkedin_mcp_zero.utils.telemetry import init_telemetry

logger = structlog.get_logger()

JobType = Literal["", "fulltime", "parttime", "contract", "internship"]


class SearchPreferences(BaseModel):
    min_salary: int = 0
    max_distance_miles: int = 50
    must_have_skills: list[str] = []
    preferred_company_size: str = "any"


class ConfirmExportPreferences(BaseModel):
    confirm: bool = False


def create_app(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings()
    init_telemetry()
    app = FastMCP("linkedin-mcp-zero")
    storage = Storage(settings)
    public = PublicAPIEngine(settings)
    llm_provider = LLMProvider(
        api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
    )
    resume = ResumeEngine(storage, llm_provider)
    matching = MatchingEngine(storage, public, llm_provider)
    browser = BrowserEngine(settings)
    voyager = VoyagerEngine(settings)
    metrics = MetricsStore(settings)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan_handler(server: FastMCP) -> AsyncGenerator[None, None]:
        yield
        logger.info("Server shutting down, cleaning up engine resources...")
        try:
            await public.close()
        except Exception as e:
            logger.warning("Failed to close public api engine during shutdown", error=str(e))
        try:
            await browser.close()
        except Exception as e:
            logger.warning("Failed to close browser engine during shutdown", error=str(e))

    app._lifespan = lifespan_handler

    READ_ONLY_ANNOTATIONS = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
        "idempotentHint": True,
    }

    WRITE_ANNOTATIONS = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "idempotentHint": True,
    }

    DESTRUCTIVE_ANNOTATIONS = {
        "readOnlyHint": False,
        "destructiveHint": True,
        "openWorldHint": False,
        "idempotentHint": False,
    }

    def async_tool(engine: str, annotations: dict[str, Any] | None = None) -> Any:
        ann = annotations or READ_ONLY_ANNOTATIONS

        def decorator(fn: Any) -> Any:
            return app.tool(annotations=ann)(track_async_tool(fn, store=metrics, settings=settings, engine=engine))

        return decorator

    def sync_tool(engine: str, annotations: dict[str, Any] | None = None) -> Any:
        ann = annotations or READ_ONLY_ANNOTATIONS

        def decorator(fn: Any) -> Any:
            return app.tool(annotations=ann)(track_sync_tool(fn, store=metrics, settings=settings, engine=engine))

        return decorator

    @async_tool("public_no_login")
    async def search_jobs(
        kw: str,
        loc: str = "",
        type: JobType = "",
        exp: int | None = None,
        remote: bool | None = None,
        age: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        """Search LinkedIn jobs by keyword/location."""
        return await public.search_jobs(kw, loc, type, exp, remote, age, limit)

    @async_tool("public_no_login")
    async def search_jobs_multi(
        kw: str,
        loc: str = "",
        limit: int = 5,
        age: int = 168,
    ) -> list[dict[str, object]]:
        """Search multiple public job boards."""
        return await multi_search(kw, loc, limit, age)

    @async_tool("public_no_login")
    async def get_job_details(id: str) -> dict[str, object]:
        """Get full public LinkedIn job details."""
        return await public.get_job_details(id)

    @async_tool("public_no_login")
    async def get_company_jobs(
        co: str,
        loc: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        """Get public jobs for a company."""
        return await public.get_company_jobs(co, loc, limit)

    @async_tool("public_no_login")
    async def get_company_profile(co: str) -> dict[str, object]:
        """Get public company profile signals."""
        return await public.get_company_profile(co)

    @async_tool("public_no_login")
    async def search_companies(kw: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, object]]:
        """Search companies from public job signals."""
        return await public.search_companies(kw, limit)

    @async_tool("public_no_login")
    async def get_job_salary(id: str) -> dict[str, object]:
        """Extract salary from public job details."""
        return await public.get_job_salary(id)

    @async_tool("public_no_login")
    async def get_job_trends(kw: str, loc: str = "") -> dict[str, object]:
        """Get hiring trends by role/location."""
        return await public.get_job_trends(kw, loc)

    @async_tool("public_no_login")
    async def get_industry_insights(ind: str) -> dict[str, object]:
        """Get public market insights for an industry."""
        return await public.get_industry_insights(ind)

    @async_tool("public_no_login")
    async def search_jobs_advanced(
        kw: str,
        loc: str = "",
        co: str = "",
        type: JobType = "",
        exp: int | None = None,
        remote: bool | None = None,
        age: str = "",
        sort: Literal["relevance", "date"] = "relevance",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        """Advanced public LinkedIn job search."""
        return await public.search_jobs_advanced(kw, loc, co, type, exp, remote, age, sort, limit)

    @sync_tool("local")
    def analyze_resume(path: str) -> dict[str, object]:
        """Parse resume PDF/DOCX/text locally."""
        return resume.analyze_resume(path)

    @async_tool("local")
    async def get_resume_insights(id: int, ctx: Context | None = None) -> dict[str, object]:
        """Get resume skill gaps and suggestions with optional LLM reasoning."""
        return await resume.get_resume_insights(id, ctx=ctx)

    @async_tool("local")
    async def match_jobs_to_resume(
        id: int,
        kw: str = "",
        loc: str = "",
        min_score: int = 60,
        limit: int = 15,
        ctx: Context | None = None,
    ) -> dict[str, object]:
        """Rank public jobs against a saved resume with optional LLM reasoning."""
        return await matching.match_jobs_to_resume(id, kw, loc, min_score, limit, ctx=ctx)

    @async_tool("local")
    async def compare_jobs(ids: list[str]) -> dict[str, object]:
        """Compare 2-5 public LinkedIn jobs."""
        return await matching.compare_jobs(ids)

    @async_tool("local", annotations=WRITE_ANNOTATIONS)
    async def export_jobs(ids: list[str], fmt: Literal["csv", "json", "xlsx"] = "csv") -> dict[str, object]:
        """Export public job details to a local file."""
        return await matching.export_jobs(ids, fmt)

    @sync_tool("local", annotations=WRITE_ANNOTATIONS)
    def save_job_alert(
        name: str,
        kw: str,
        loc: str = "",
        freq: Literal["daily", "weekly"] = "daily",
    ) -> dict[str, object]:
        """Save a recurring job search."""
        return storage.save_alert(name, kw, loc, freq)

    @sync_tool("local")
    def get_saved_alerts() -> list[dict[str, object]]:
        """List saved job alerts."""
        return storage.list_alerts()

    @async_tool("public_no_login")
    async def check_saved_alerts(ids: list[int] | None = None) -> list[dict[str, object]]:
        """Run saved alerts and report new matches."""
        results = []
        for alert in storage.selected_alerts(ids):
            jobs = await public.search_jobs(
                kw=str(alert["kw"]),
                loc=str(alert["loc"] or ""),
                limit=DEFAULT_LIMIT,
            )
            seen = set(json.loads(str(alert.get("last_ids") or "[]")))
            current = [str(job.get("id", "")) for job in jobs if job.get("id")]
            new_jobs = [job for job in jobs if str(job.get("id", "")) not in seen]
            storage.update_alert_seen(int(alert["id"]), current)
            results.append(
                {
                    "alert_id": alert["id"],
                    "name": alert["name"],
                    "new_matches": len(new_jobs),
                    "jobs": new_jobs,
                }
            )
        return results

    if settings.enable_browser:

        @async_tool("browser_readonly")
        async def get_my_profile() -> dict[str, object]:
            """Get your LinkedIn profile via opt-in read-only browser mode."""
            return await browser.get_my_profile()

        @async_tool("browser_readonly")
        async def get_person_profile(uname: str) -> dict[str, object]:
            """Get a person's LinkedIn profile via opt-in read-only browser mode."""
            return await browser.get_person_profile(uname)

        @async_tool("browser_readonly")
        async def search_people(
            kw: str,
            loc: str = "",
            co: str = "",
            limit: int = DEFAULT_LIMIT,
        ) -> dict[str, object]:
            """Search people via opt-in read-only browser mode."""
            return await browser.search_people(kw=kw, loc=loc, co=co, limit=limit)

        @async_tool("browser_readonly")
        async def get_my_connections(limit: int = 50) -> dict[str, object]:
            """Get your LinkedIn connections via opt-in read-only browser mode."""
            return await browser.get_my_connections(limit=limit)

        @async_tool("browser_readonly")
        async def get_inbox(limit: int = DEFAULT_LIMIT) -> dict[str, object]:
            """Get recent LinkedIn conversations via opt-in read-only browser mode."""
            return await browser.get_inbox(limit=limit)

        @async_tool("browser_readonly")
        async def get_conversation(id: str) -> dict[str, object]:
            """Read a LinkedIn conversation via opt-in read-only browser mode."""
            return await browser.get_conversation(id)

        @async_tool("browser_readonly")
        async def get_feed(limit: int = 5) -> dict[str, object]:
            """Get LinkedIn home feed via opt-in read-only browser mode."""
            return await browser.get_feed(limit=limit)

        @async_tool("browser_readonly")
        async def get_notifications(limit: int = DEFAULT_LIMIT) -> dict[str, object]:
            """Get LinkedIn notifications via opt-in read-only browser mode."""
            return await browser.get_notifications(limit=limit)

        @async_tool("browser_readonly")
        async def get_sidebar_profiles() -> dict[str, object]:
            """Get sidebar profile suggestions via opt-in read-only browser mode."""
            return await browser.get_sidebar_profiles()

        @async_tool("browser_readonly")
        async def get_company_employees(
            co: str,
            kw: str = "",
            limit: int = 25,
        ) -> dict[str, object]:
            """Get company employees via opt-in read-only browser mode."""
            return await browser.get_company_employees(co=co, kw=kw, limit=limit)

        @async_tool("browser_readonly")
        async def check_session() -> dict[str, object]:
            """Check CDP browser and LinkedIn session readiness."""
            return await browser.check_session()

    @async_tool("system")
    async def get_engine_status() -> dict[str, object]:
        """Show available engines."""
        browser_status = await browser.status()
        registered_count = sum(1 for k in app.local_provider._components if k.startswith("tool:"))
        return {
            "tool_count": registered_count,
            "catalog_tool_count": len(TOOLS),
            "engines": [
                {
                    "name": "public_apis",
                    "risk": "public_no_login_read_only",
                    "available": True,
                    "tools": 9,
                },
                {
                    "name": "multi_board",
                    "risk": "public_no_login_read_only",
                    "available": True,
                    "tools": 1,
                    "mode": "all_5_boards" if _jobspy_available() else "linkedin_fallback",
                    "hint": None if _jobspy_available() else "Install with `--with-extra multi` for all 5 boards.",
                },
                {
                    "name": "resume",
                    "risk": "local_zero_account_risk",
                    "available": True,
                    "tools": 2,
                },
                {
                    "name": "matching",
                    "risk": "local_zero_account_risk",
                    "available": True,
                    "tools": 3,
                },
                {
                    "name": "storage",
                    "risk": "local_zero_account_risk",
                    "available": True,
                    "tools": 3,
                },
                {
                    "name": "cdp_browser",
                    "risk": "browser_readonly_account_risk",
                    "enabled": settings.enable_browser,
                    "tools": 11 if settings.enable_browser else 0,
                    **browser_status,
                },
                {
                    "name": "voyager",
                    "risk": "disabled_private_api_risk",
                    "available": settings.enable_voyager and bool(settings.li_at),
                    "enabled": settings.enable_voyager,
                    "tools": 1 if settings.enable_voyager else 0,
                },
            ],
            "runtime": detect_runtime(settings.data_dir),
            "cache": public.cache.stats(),
            "data_dir": str(storage.base_dir),
            "token_tracking": {
                "estimated": "ceil(response_chars / 4)",
                "exact_enabled": settings.exact_token_count and bool(settings.anthropic_api_key),
                "stores_payloads": False,
            },
        }

    @sync_tool("system")
    def get_help(tool: str = "") -> dict[str, object]:
        """Show tool documentation."""
        return tool_help(tool)

    @app.tool(annotations=READ_ONLY_ANNOTATIONS)
    def get_usage_stats(limit: int = 50) -> dict[str, object]:
        """Show recent local MCP usage and token estimates."""
        return {
            "calls": metrics.recent_calls(limit),
            "token_counting": "anthropic_count_tokens"
            if settings.exact_token_count and settings.anthropic_api_key
            else "estimate",
            "estimate_formula": "ceil(response_chars / 4)",
            "stores_payloads": False,
            "exact_count_external_send": bool(settings.exact_token_count and settings.anthropic_api_key),
            "token_count_model": settings.token_count_model,
        }

    @app.tool(annotations=READ_ONLY_ANNOTATIONS)
    def get_tool_usage_summary() -> dict[str, object]:
        """Show local aggregate MCP usage by tool."""
        summary = metrics.summary()
        summary["stores_payloads"] = False
        summary["exact_count_external_send"] = bool(settings.exact_token_count and settings.anthropic_api_key)
        return summary

    @app.tool(annotations=DESTRUCTIVE_ANNOTATIONS)
    def reset_usage_stats(confirm: bool = False) -> dict[str, object]:
        """Reset local usage metrics."""
        if not confirm:
            return {"error": "Pass confirm=true to reset usage stats."}
        return {"rows_deleted": metrics.reset()}

    if settings.enable_voyager:

        @async_tool("voyager")
        async def get_profile_voyager(uname: str) -> dict[str, object]:
            """Get a profile through gated Voyager mode."""
            return await voyager.get_profile(uname)

    # --- Week 1 MCP Resources ---
    @app.resource("jobs://trending/{kw}")
    async def trending_jobs_resource(kw: str) -> str:
        """Live feed of trending jobs for a keyword."""
        jobs = await public.search_jobs(kw, limit=5)
        return json.dumps(jobs, indent=2)

    @app.resource("alerts://saved")
    def saved_alerts_resource() -> str:
        """Your saved job alerts as a live resource."""
        return json.dumps(storage.list_alerts(), indent=2)

    @app.resource("resume://{id}/summary")
    def resume_summary(id: int) -> str:
        """Quick resume summary without calling a tool."""
        resume = storage.get_resume(id)
        if not resume:
            return f"Resume {id} not found"
        return f"{resume.get('name', 'Unknown')} — {', '.join(resume.get('skills', [])[:5])}"

    @app.resource("company://{name}/profile")
    async def company_resource(name: str) -> str:
        """Company profile as a URI-addressable resource."""
        profile = await public.get_company_profile(name)
        return json.dumps(profile, indent=2)

    @app.resource("status://engines")
    async def engine_status_resource() -> str:
        """Engine health — always available as context."""
        status_info = await browser.status()
        return json.dumps(status_info, indent=2)

    # --- Week 1 MCP Prompts ---
    @app.prompt()
    def daily_job_digest(kw: str = "python", loc: str = "remote") -> str:
        """Generate a daily job search digest."""
        return f"""Search for the latest {kw} jobs in {loc}.
For each job found:
1. Extract the title, company, salary, and key skills
2. Compare against my saved resumes
3. Highlight any new postings from the last 24 hours
4. Format as a concise briefing with match scores"""

    @app.prompt()
    def company_deep_dive(company: str) -> str:
        """Full intelligence report on a company."""
        return f"""Research {company} thoroughly:
1. Get their open job listings and analyze hiring patterns
2. Identify their tech stack from job descriptions
3. Count open positions by department
4. Estimate company growth signals from hiring velocity
5. Compare their salary ranges to market averages"""

    @app.prompt()
    def career_path_advisor(role: str, experience_years: int = 3) -> str:
        """AI career advisor based on real LinkedIn data."""
        return f"""Based on real-time LinkedIn data for {role} with ~{experience_years} years experience:
1. Search for jobs matching this profile
2. Identify the most in-demand skills for this role
3. Find salary ranges from actual job postings
4. Suggest skills to learn next based on senior role requirements
5. Identify companies actively hiring for this profile"""

    @app.prompt()
    def interview_prep(company: str, role: str) -> str:
        """Prepare for an interview using public LinkedIn data."""
        return f"""Help me prepare for a {role} interview at {company}:
1. Get the company's recent job postings to understand their tech stack
2. Analyze the specific job requirements
3. Identify common skills mentioned across their openings
4. Research company culture signals from their job descriptions
5. Suggest questions I should ask based on their hiring patterns"""

    # --- Week 2-4 MCP Sampling & Elicitation Tools ---
    @app.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def smart_match_jobs(resume_id: int, ctx: Context | None = None) -> dict[str, object]:
        """AI-powered job matching using the client's LLM for reasoning."""
        resume = storage.get_resume(resume_id)
        if not resume:
            return {"error": "resume_not_found", "id": resume_id}
        skills = resume.get("skills", [])
        jobs = await public.search_jobs(kw=" ".join(skills[:3]) if skills else "software engineer", limit=10)

        prompt = f"""You are an expert career advisor. Given this resume:
Name: {resume.get("name")}
Skills: {", ".join(skills)}
Summary: {resume.get("summary", "")[:300]}

And these job listings:
{json.dumps(jobs[:5], indent=2)}

Rank the top jobs by fit. Explain why they match and identify any skill gaps.
Return a concise summary with match scores."""

        analysis = await llm_provider.generate(
            prompt=prompt,
            system_prompt="You are a precise career matching engine. Be concise.",
            ctx=ctx,
        )
        return {"analysis": analysis, "jobs_analyzed": len(jobs)}

    @app.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def generate_cover_letter(job_id: str, resume_id: int, ctx: Context | None = None) -> dict[str, object]:
        """Generate a tailored cover letter using the client's LLM."""
        job = await public.get_job_details(job_id)
        resume = storage.get_resume(resume_id)
        if not resume:
            return {"error": "resume_not_found", "id": resume_id}

        prompt = f"""Write a concise, compelling cover letter (max 200 words) for:
JOB: {job.get("t")} at {job.get("co")}
Requirements: {str(job.get("desc") or "")[:500]}
CANDIDATE:
Name: {resume.get("name")}
Skills: {", ".join(str(s) for s in resume.get("skills") or [])}
Experience: {str(resume.get("summary") or "")[:300]}"""

        cover_letter = await llm_provider.generate(
            prompt=prompt,
            system_prompt="You are a professional cover letter writer.",
            ctx=ctx,
        )
        return {"cover_letter": cover_letter}

    @app.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def analyze_salary_offer(job_id: str, ctx: Context | None = None) -> dict[str, object]:
        """AI-powered salary analysis using real market data and client's LLM."""
        job = await public.get_job_details(job_id)
        trends = {}
        if hasattr(public, "get_job_trends"):
            trends = await public.get_job_trends(str(job.get("t") or ""), str(job.get("loc") or ""))

        prompt = f"""Analyze this job's compensation:
Job: {job.get("t")} at {job.get("co")} in {job.get("loc")}
Listed salary: {job.get("sal", "Not disclosed")}
Market data context: {json.dumps(trends)}"""

        analysis = await llm_provider.generate(
            prompt=prompt,
            system_prompt="You are a professional compensation analyst.",
            ctx=ctx,
        )
        return {"job_id": job_id, "analysis": analysis}

    @app.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def personalized_job_hunt(kw: str, ctx: Context) -> dict[str, object]:
        """Interactive job search that asks you what matters most."""
        result = await ctx.elicit(
            message="Customize your job search preferences:",
            response_type=cast(Any, SearchPreferences),
        )
        if result.action != "accept":
            return {"status": "cancelled", "reason": result.action}

        prefs: Any = result.data
        jobs = await public.search_jobs(kw, limit=25)

        import asyncio

        jobs_with_ids = [j for j in jobs if j.get("id")]
        tasks = [public.get_job_details(str(j["id"])) for j in jobs_with_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        filtered = []
        for job, detail_res in zip(jobs_with_ids, results, strict=True):
            job_detail: dict[str, Any] = {}
            if not isinstance(detail_res, BaseException):
                job_detail = detail_res

            merged_job = {**job, **job_detail}
            job_text = " ".join(str(v) for v in merged_job.values())

            # 1. Skills match
            skills_match = True
            for skill in prefs.must_have_skills:
                if skill.lower() not in job_text.lower():
                    skills_match = False
                    break
            if not skills_match:
                continue

            # 2. Salary match
            sal_str = str(merged_job.get("sal", ""))
            if prefs.min_salary > 0 and sal_str:
                import re

                sal_match = re.search(r"(\d+)", sal_str)
                if sal_match:
                    sal_val = int(sal_match.group(1))
                    if "K" in sal_str.upper() or "k" in sal_str:
                        sal_val *= 1000
                    if sal_val < prefs.min_salary:
                        continue

            # 3. Remote/Distance matching
            loc_str = str(merged_job.get("loc", "")).lower()
            if prefs.max_distance_miles < 20 and "remote" not in loc_str:
                continue

            filtered.append(merged_job)

        return {"jobs": filtered[:10], "prefs_applied": prefs.model_dump()}

    @app.tool(annotations=WRITE_ANNOTATIONS)
    async def confirm_export(ids: list[str], fmt: str, ctx: Context) -> dict[str, object]:
        """Export jobs with user confirmation."""
        result = await ctx.elicit(
            message=f"Are you sure you want to export {len(ids)} jobs in {fmt} format?",
            response_type=cast(Any, ConfirmExportPreferences),
        )
        if result.action != "accept":
            return {"status": "cancelled", "reason": "User did not confirm"}
        confirm_data: Any = result.data
        if not confirm_data.confirm:
            return {"status": "cancelled", "reason": "User did not confirm"}

        return await matching.export_jobs(ids, fmt)

    @app.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def get_resume_insights_advanced(id: int, ctx: Context | None = None) -> dict[str, object]:
        """Get advanced AI-powered insights on a resume using LLM reasoning."""
        resume_data = storage.get_resume(id)
        if not resume_data:
            return {"error": "resume_not_found", "id": id}

        prompt = f"""Analyze this candidate resume profile:
Name: {resume_data.get("name")}
Skills: {", ".join(resume_data.get("skills", []))}
Summary: {resume_data.get("summary", "")}

Provide:
1. A brief executive summary of their profile
2. Their top 3 strengths
3. Key areas of improvement / missing skills for modern software engineering roles
4. Tailored recommendations to make their resume stand out"""

        analysis = await llm_provider.generate(
            prompt=prompt,
            system_prompt="You are an expert technical recruiter and career coach.",
            ctx=ctx,
        )
        return {"id": id, "insights": analysis}

    @app.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def deep_industry_analysis(industry: str, ctx: Context | None = None) -> dict[str, object]:
        """Full industry analysis with progress updates."""
        jobs = await public.search_jobs(kw=industry, limit=10)

        analyzed = []
        for i, job in enumerate(jobs[:5]):
            if ctx is not None:
                await ctx.report_progress(
                    progress=i + 1,
                    total=5,
                    message=f"Analyzing: {job.get('t', 'unknown')} at {job.get('co', 'unknown')}",
                )
            job_id = job.get("id")
            if job_id:
                try:
                    detail = await public.get_job_details(str(job_id))
                    analyzed.append(detail)
                except Exception:
                    analyzed.append(job)
            else:
                analyzed.append(job)

        summary = f"Analyzed {len(analyzed)} jobs in the {industry} industry."
        return {"summary": summary, "jobs": analyzed}

    from starlette.requests import Request
    from starlette.responses import JSONResponse

    @app.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        """Health check endpoint for streamable-http deployment."""
        status_info = await browser.status()
        return JSONResponse(
            {
                "status": "ok",
                "engines": status_info,
            }
        )

    @app.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
    async def oauth_protected_resource(request: Request) -> JSONResponse:
        """Protected resource metadata endpoint as per RFC 9728."""
        return JSONResponse(
            {
                "resource": f"http://{settings.host}:{settings.port}",
                "authorization_servers": [settings.oauth_server_url] if settings.oauth_server_url else [],
                "scopes_supported": ["jobs:read", "profile:read", "alerts:manage"],
                "bearer_methods_supported": ["header"],
            }
        )

    return app


def _jobspy_available() -> bool:
    try:
        import jobspy  # noqa: F401
    except ImportError:
        return False
    return True
