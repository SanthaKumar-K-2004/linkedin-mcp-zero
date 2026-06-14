from __future__ import annotations

import json
from typing import Literal

from fastmcp import FastMCP

from linkedin_mcp_zero.config.autodetect import detect_runtime
from linkedin_mcp_zero.config.defaults import DEFAULT_LIMIT
from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.engines.browser import BrowserEngine
from linkedin_mcp_zero.engines.matching import MatchingEngine
from linkedin_mcp_zero.engines.multi_board import search_jobs_multi as multi_search
from linkedin_mcp_zero.engines.public_api import PublicAPIEngine
from linkedin_mcp_zero.engines.resume import ResumeEngine
from linkedin_mcp_zero.engines.voyager import VoyagerEngine
from linkedin_mcp_zero.server.catalog import TOOLS, tool_help
from linkedin_mcp_zero.storage.db import Storage

JobType = Literal["", "fulltime", "parttime", "contract", "internship"]


def create_app(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings()
    app = FastMCP("linkedin-mcp-zero")
    storage = Storage(settings)
    public = PublicAPIEngine(settings)
    resume = ResumeEngine(storage)
    matching = MatchingEngine(storage, public)
    browser = BrowserEngine(settings)
    voyager = VoyagerEngine(settings)

    @app.tool()
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

    @app.tool()
    async def search_jobs_multi(
        kw: str,
        loc: str = "",
        limit: int = 5,
        age: int = 168,
    ) -> list[dict[str, object]]:
        """Search multiple public job boards."""
        return await multi_search(kw, loc, limit, age)

    @app.tool()
    async def get_job_details(id: str) -> dict[str, object]:
        """Get full public LinkedIn job details."""
        return await public.get_job_details(id)

    @app.tool()
    async def get_company_jobs(
        co: str,
        loc: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, object]]:
        """Get public jobs for a company."""
        return await public.get_company_jobs(co, loc, limit)

    @app.tool()
    async def get_company_profile(co: str) -> dict[str, object]:
        """Get public company profile signals."""
        return await public.get_company_profile(co)

    @app.tool()
    async def search_companies(kw: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, object]]:
        """Search companies from public job signals."""
        return await public.search_companies(kw, limit)

    @app.tool()
    async def get_job_salary(id: str) -> dict[str, object]:
        """Extract salary from public job details."""
        return await public.get_job_salary(id)

    @app.tool()
    async def get_job_trends(kw: str, loc: str = "") -> dict[str, object]:
        """Get hiring trends by role/location."""
        return await public.get_job_trends(kw, loc)

    @app.tool()
    async def get_industry_insights(ind: str) -> dict[str, object]:
        """Get public market insights for an industry."""
        return await public.get_industry_insights(ind)

    @app.tool()
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

    @app.tool()
    def analyze_resume(path: str) -> dict[str, object]:
        """Parse resume PDF/DOCX/text locally."""
        return resume.analyze_resume(path)

    @app.tool()
    def get_resume_insights(id: int) -> dict[str, object]:
        """Get local resume skill gaps and suggestions."""
        return resume.get_resume_insights(id)

    @app.tool()
    async def match_jobs_to_resume(
        id: int,
        kw: str = "",
        loc: str = "",
        min_score: int = 60,
        limit: int = 15,
    ) -> dict[str, object]:
        """Rank public jobs against a saved resume."""
        return await matching.match_jobs_to_resume(id, kw, loc, min_score, limit)

    @app.tool()
    async def compare_jobs(ids: list[str]) -> dict[str, object]:
        """Compare 2-5 public LinkedIn jobs."""
        return await matching.compare_jobs(ids)

    @app.tool()
    async def export_jobs(
        ids: list[str], fmt: Literal["csv", "json", "xlsx"] = "csv"
    ) -> dict[str, object]:
        """Export public job details to a local file."""
        return await matching.export_jobs(ids, fmt)

    @app.tool()
    def save_job_alert(
        name: str,
        kw: str,
        loc: str = "",
        freq: Literal["daily", "weekly"] = "daily",
    ) -> dict[str, object]:
        """Save a recurring job search."""
        return storage.save_alert(name, kw, loc, freq)

    @app.tool()
    def get_saved_alerts() -> list[dict[str, object]]:
        """List saved job alerts."""
        return storage.list_alerts()

    @app.tool()
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

    @app.tool()
    async def get_my_profile() -> dict[str, object]:
        """Get your LinkedIn profile via CDP browser."""
        return await browser.get_my_profile()

    @app.tool()
    async def get_person_profile(uname: str) -> dict[str, object]:
        """Get a person's LinkedIn profile via CDP browser."""
        return await browser.get_person_profile(uname)

    @app.tool()
    async def search_people(
        kw: str,
        loc: str = "",
        co: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, object]:
        """Search people via CDP browser."""
        return await browser.search_people(kw=kw, loc=loc, co=co, limit=limit)

    @app.tool()
    async def get_my_connections(limit: int = 50) -> dict[str, object]:
        """Get your LinkedIn connections via CDP browser."""
        return await browser.get_my_connections(limit=limit)

    @app.tool()
    async def get_inbox(limit: int = DEFAULT_LIMIT) -> dict[str, object]:
        """Get recent LinkedIn conversations via CDP browser."""
        return await browser.get_inbox(limit=limit)

    @app.tool()
    async def get_conversation(id: str) -> dict[str, object]:
        """Read a LinkedIn conversation via CDP browser."""
        return await browser.get_conversation(id)

    @app.tool()
    async def get_feed(limit: int = 5) -> dict[str, object]:
        """Get LinkedIn home feed via CDP browser."""
        return await browser.get_feed(limit=limit)

    @app.tool()
    async def get_notifications(limit: int = DEFAULT_LIMIT) -> dict[str, object]:
        """Get LinkedIn notifications via CDP browser."""
        return await browser.get_notifications(limit=limit)

    @app.tool()
    async def get_sidebar_profiles() -> dict[str, object]:
        """Get sidebar profile suggestions via CDP browser."""
        return await browser.get_sidebar_profiles()

    @app.tool()
    async def get_company_employees(
        co: str,
        kw: str = "",
        limit: int = 25,
    ) -> dict[str, object]:
        """Get company employees via CDP browser."""
        return await browser.get_company_employees(co=co, kw=kw, limit=limit)

    @app.tool()
    async def check_session() -> dict[str, object]:
        """Check CDP browser and LinkedIn session readiness."""
        return await browser.check_session()

    @app.tool()
    async def get_engine_status() -> dict[str, object]:
        """Show available engines."""
        browser_status = await browser.status()
        return {
            "tool_count": len(TOOLS),
            "engines": [
                {"name": "public_apis", "risk": "zero", "available": True, "tools": 10},
                {
                    "name": "resume",
                    "risk": "zero",
                    "available": True,
                    "tools": 2,
                },
                {"name": "matching", "risk": "zero", "available": True, "tools": 3},
                {"name": "storage", "risk": "zero", "available": True, "tools": 3},
                {"name": "cdp_browser", "risk": "minimal", "tools": 10, **browser_status},
                {
                    "name": "voyager",
                    "risk": "low",
                    "available": settings.enable_voyager and bool(settings.li_at),
                    "enabled": settings.enable_voyager,
                    "tools": 1,
                },
            ],
            "runtime": detect_runtime(settings.data_dir),
            "cache": public.cache.stats(),
            "data_dir": str(storage.base_dir),
        }

    @app.tool()
    def get_help(tool: str = "") -> dict[str, object]:
        """Show tool documentation."""
        return tool_help(tool)

    @app.tool()
    async def get_profile_voyager(uname: str) -> dict[str, object]:
        """Get a profile through gated Voyager mode."""
        return await voyager.get_profile(uname)

    return app
