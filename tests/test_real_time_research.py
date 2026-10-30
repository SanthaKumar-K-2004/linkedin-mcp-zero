from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.config.skills import COMMON_SKILLS, extract_skills_from_text
from linkedin_mcp_zero.engines.matching import MatchingEngine
from linkedin_mcp_zero.engines.public_api import PublicAPIEngine
from linkedin_mcp_zero.engines.resume import ResumeEngine
from linkedin_mcp_zero.engines.voyager import VoyagerEngine
from linkedin_mcp_zero.storage.db import Storage
from linkedin_mcp_zero.utils.oauth import OAuthMiddleware


@pytest.mark.asyncio
async def test_real_time_resume_insights_from_live_market(tmp_path) -> None:
    """Verify that get_resume_insights performs real-time market research and identifies live in-demand skills."""
    storage = Storage(Settings(data_dir=str(tmp_path)))
    resume_id = storage.save_resume(
        "/dummy/resume.txt",
        {
            "name": "Alice Developer",
            "skills": ["Python", "FastAPI"],
            "summary": "Backend engineer building high-performance microservices",
        },
    )

    mock_public = AsyncMock()
    mock_public.search_jobs.return_value = [
        {
            "id": "1001",
            "t": "Senior Python Engineer",
            "co": "TechCorp",
            "loc": "Remote",
            "desc": "Seeking Python engineer with Docker, Kubernetes, AWS, and PostgreSQL experience.",
        },
        {
            "id": "1002",
            "t": "Backend Architect",
            "co": "CloudSystems",
            "loc": "Remote",
            "desc": "Required: Python, FastAPI, Docker, Redis, and Terraform.",
        },
    ]

    engine = ResumeEngine(storage, public=mock_public)
    insights = await engine.get_resume_insights(resume_id)

    assert insights["id"] == resume_id
    assert insights["market_sample_jobs"] == 2
    assert "Python" in insights["strengths"]
    assert "Docker" in insights["gap_skills"]
    assert "Kubernetes" in insights["gap_skills"] or "AWS" in insights["gap_skills"]
    assert "TechCorp" not in insights["market_pos"]  # Verify structured position format
    assert "High-frequency market requirement" in insights["suggestions"][0]
    mock_public.search_jobs.assert_called_once()


@pytest.mark.asyncio
async def test_adaptive_domain_ecosystem_frontend_vs_backend(tmp_path) -> None:
    """Verify that candidate skills dynamically infer their respective domains without hardcoded backend bias."""
    storage = Storage(Settings(data_dir=str(tmp_path)))

    # Frontend candidate
    fe_id = storage.save_resume(
        "/dummy/fe.txt",
        {"name": "Frontend Dev", "skills": ["React", "HTML", "CSS"]},
    )
    engine = ResumeEngine(storage, public=None)
    fe_insights = await engine.get_resume_insights(fe_id)

    assert "React" in fe_insights["strengths"]
    assert "TypeScript" in fe_insights["gap_skills"] or "JavaScript" in fe_insights["gap_skills"]
    assert "Kubernetes" not in fe_insights["gap_skills"]  # No backend bias for frontend dev!

    # Mobile candidate
    mobile_id = storage.save_resume(
        "/dummy/mobile.txt",
        {"name": "Mobile Dev", "skills": ["Swift", "iOS"]},
    )
    mobile_insights = await engine.get_resume_insights(mobile_id)
    assert "Swift" in mobile_insights["strengths"]
    assert any(k in mobile_insights["gap_skills"] for k in ["Kotlin", "React Native", "Flutter", "Dart"])


def test_expanded_skill_taxonomy() -> None:
    """Verify that the skill taxonomy covers multi-word and punctuation-sensitive technologies."""
    assert len(COMMON_SKILLS) >= 100
    sample_text = "Expert in C++, C#, .NET, Spring Boot, Next.js, Apache Kafka, and React Native."
    extracted = extract_skills_from_text(sample_text)

    assert "C++" in extracted
    assert "C#" in extracted
    assert ".NET" in extracted
    assert "Spring Boot" in extracted
    assert "Next.js" in extracted
    assert "Apache Kafka" in extracted or "Kafka" in extracted
    assert "React Native" in extracted


@pytest.mark.asyncio
async def test_dynamic_match_reasoning_in_matching_engine(tmp_path) -> None:
    """Verify that MatchingEngine produces dynamic reasoning with applicant counts and repost viability."""
    storage = Storage(Settings(data_dir=str(tmp_path)))
    resume_id = storage.save_resume(
        "/dummy/path",
        {
            "name": "Bob",
            "skills": ["Python", "Docker"],
            "summary": "Experienced Python and Docker developer building cloud systems.",
        },
    )

    mock_public = AsyncMock()
    mock_public.search_jobs.return_value = [
        {
            "id": "2001",
            "t": "Python Developer",
            "co": "Acme",
            "loc": "Remote",
            "desc": "Looking for Python, Docker, and AWS. Reposted 2 times. 45 applicants.",
        }
    ]
    mock_public.get_job_details.return_value = {
        "id": "2001",
        "title": "Python Developer",
        "company": "Acme",
        "desc": "Looking for Python, Docker, and AWS. Reposted 2 times. 45 applicants.",
    }

    matching = MatchingEngine(storage, mock_public)
    result = await matching.match_jobs_to_resume(resume_id, min_score=40, limit=5)

    assert len(result["matches"]) == 1
    match = result["matches"][0]
    # Check dynamic 'why' string contains real attributes
    assert "Direct match on" in match["why"]
    assert "Python" in match["why"] or "Docker" in match["why"]
    assert "viability" in match["why"]
    assert "45 applicants" in match["why"]


@pytest.mark.asyncio
async def test_voyager_engine_live_request_dispatch() -> None:
    """Verify that VoyagerEngine builds authentic live requests with li_at cookie and headers."""
    settings = Settings(enable_voyager=True, li_at="AQEDAtestcookie123")
    engine = VoyagerEngine(settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "elements": [
            {
                "firstName": "Satya",
                "lastName": "Nadella",
                "headline": "Chairman and CEO at Microsoft",
                "summary": "Building platforms and tools",
                "industryName": "Software Development",
                "geoLocationName": "Greater Seattle Area",
            }
        ]
    }

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp

    with patch.object(engine, "_get_session", return_value=mock_session):
        profile = await engine.get_profile("satyanadella")

        assert profile["available"] is True
        assert profile["source"] == "live_voyager_api"
        assert profile["name"] == "Satya Nadella"
        assert profile["headline"] == "Chairman and CEO at Microsoft"
        assert profile["industry"] == "Software Development"

        mock_session.get.assert_called_once()
        args, kwargs = mock_session.get.call_args
        assert "satyanadella/profileView" in args[0]
        assert "li_at=AQEDAtestcookie123" in kwargs["headers"]["Cookie"]
        assert kwargs["headers"]["csrf-token"] == "ajax:0"

    await engine.close()


def test_cors_allowed_origins_restricted_by_default() -> None:
    """Verify CORS origins default to localhost addresses rather than wildcard."""
    settings = Settings()
    assert "*" not in settings.cors_allowed_origins
    assert "http://localhost" in settings.cors_allowed_origins
    assert "http://127.0.0.1" in settings.cors_allowed_origins


@pytest.mark.asyncio
async def test_oauth_middleware_persistent_client_pooling() -> None:
    """Verify OAuthMiddleware uses a persistent connection pool across requests."""
    settings = Settings(
        oauth_server_url="https://auth.example.com",
        oauth_client_id="client123",
        oauth_client_secret="secret456",
    )
    dummy_app = AsyncMock()
    mw = OAuthMiddleware(dummy_app, None, settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"active": True}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        is_valid_1 = await mw._validate_token("token_abc")
        is_valid_2 = await mw._validate_token("token_xyz")

        assert is_valid_1 is True
        assert is_valid_2 is True
        assert mock_post.call_count == 2
        # Client should be instantiated and reused
        assert mw._client is not None

    await mw.close()
    assert mw._client is None


@pytest.mark.asyncio
async def test_public_api_engine_higher_level_methods() -> None:
    """Verify PublicAPIEngine methods: get_company_jobs, search_companies, get_company_profile, get_job_trends, get_industry_insights."""
    settings = Settings()
    engine = PublicAPIEngine(settings)

    mock_jobs = [
        {"id": "301", "t": "Software Engineer", "co": "Google", "loc": "Mountain View, CA", "desc": "Python and Go"},
        {"id": "302", "t": "Staff SRE", "co": "Google", "loc": "Remote", "desc": "Kubernetes and Linux"},
        {"id": "303", "t": "Frontend Dev", "co": "Meta", "loc": "Menlo Park, CA", "desc": "React and TypeScript"},
    ]

    with (
        patch.object(engine, "search_jobs", return_value=mock_jobs),
        patch.object(engine, "get_job_details", return_value={"id": "301", "skills": ["Python", "Go"]}),
    ):
        # Test get_company_jobs
        google_jobs = await engine.get_company_jobs(co="Google")
        assert len(google_jobs) == 2
        assert all("Google" in j["co"] for j in google_jobs)

        # Test search_companies
        companies = await engine.search_companies(kw="engineer")
        assert len(companies) >= 2
        assert any(c["name"] == "Google" for c in companies)

        # Test get_company_profile
        profile = await engine.get_company_profile(co="Google")
        assert profile["name"] == "Google"
        assert profile["open_jobs_seen"] == 2
        assert "Remote" in profile["loc"] or "Mountain View, CA" in profile["loc"]

        # Test get_job_trends
        trends = await engine.get_job_trends(kw="engineer")
        assert trends["sample"] == 3
        assert trends["top_companies"][0]["name"] == "Google"
        assert trends["remote_pct"] == 33  # 1 out of 3 is remote

        # Test get_industry_insights
        insights = await engine.get_industry_insights(ind="tech")
        assert insights["industry"] == "tech"
        assert insights["sample"] == 3

    await engine.close()
