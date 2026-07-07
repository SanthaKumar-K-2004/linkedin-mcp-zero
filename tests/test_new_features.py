from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from linkedin_mcp_zero.engines.matching import MatchingEngine
from linkedin_mcp_zero.engines.public_api import PublicAPIEngine
from linkedin_mcp_zero.server.app import create_app
from linkedin_mcp_zero.storage.db import Storage
from linkedin_mcp_zero.utils.circuit_breaker import CircuitBreaker
from linkedin_mcp_zero.utils.errors import UpstreamError


def test_circuit_breaker() -> None:
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    assert cb.state == "CLOSED"
    assert cb.allow_request() is True

    cb.record_failure()
    assert cb.state == "CLOSED"

    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.allow_request() is False

    with pytest.raises(UpstreamError):
        cb.check()

    time.sleep(0.15)
    assert cb.allow_request() is True
    assert cb.state == "HALF-OPEN"

    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0


def test_semantic_fallback() -> None:
    storage = MagicMock(spec=Storage)
    public = MagicMock(spec=PublicAPIEngine)
    engine = MatchingEngine(storage, public)

    sim = engine._semantic_score("Python JavaScript AWS", "Python JavaScript AWS")
    assert pytest.approx(sim, 0.01) == 1.0

    sim2 = engine._semantic_score("Python JavaScript AWS", "Docker Kubernetes Golang")
    assert sim2 == 0.0

    sim3 = engine._semantic_score("Python JavaScript", "Python Go Rust")
    assert 0.0 < sim3 < 1.0


@pytest.mark.anyio
async def test_app_resources_and_prompts() -> None:
    app = create_app()

    prompts = [p.name for p in await app.list_prompts()]
    assert "daily_job_digest" in prompts
    assert "company_deep_dive" in prompts
    assert "career_path_advisor" in prompts
    assert "interview_prep" in prompts

    resources = [str(r.uri) for r in await app.list_resources()]
    assert any("saved" in r for r in resources)
    assert any("engines" in r for r in resources)

    templates = [str(t.uri_template) for t in await app.list_resource_templates()]
    assert any("trending" in t for t in templates)
    assert any("summary" in t for t in templates)
    assert any("profile" in t for t in templates)

    tools = [t.name for t in await app.list_tools()]
    assert "smart_match_jobs" in tools
    assert "generate_cover_letter" in tools
    assert "analyze_salary_offer" in tools
    assert "personalized_job_hunt" in tools
    assert "confirm_export" in tools
    assert "get_resume_insights_advanced" in tools


@pytest.mark.anyio
async def test_llm_provider() -> None:
    from linkedin_mcp_zero.utils.llm import LLMProvider

    provider = LLMProvider()
    response = await provider.generate("Analyze my resume", system_prompt="Recruiter")
    assert "[Local Fallback Analysis]" in response
    assert "Analyze my resume" in response


@pytest.mark.anyio
async def test_concurrent_compare_and_export(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.engines.matching import MatchingEngine
    from linkedin_mcp_zero.engines.public_api import PublicAPIEngine

    storage = Storage(Settings(data_dir=str(tmp_path)))
    public = MagicMock(spec=PublicAPIEngine)
    public.get_job_details = AsyncMock(
        return_value={
            "id": "123",
            "co": "Google",
            "t": "Python Engineer",
            "sal": "$150,000",
            "loc": "Remote",
            "type": "Full-time",
            "url": "https://linkedin.com/jobs/view/123",
        }
    )

    engine = MatchingEngine(storage, public)
    res = await engine.compare_jobs(["123"])
    assert res["rows"][0][0] == "Google"

    exp = await engine.export_jobs(["123"], fmt="json")
    assert exp["count"] == 1
    assert "jobs_export.json" in exp["path"]
