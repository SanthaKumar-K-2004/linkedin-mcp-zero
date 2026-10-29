from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from linkedin_mcp_zero.cache.ttl_cache import TTLCache
from linkedin_mcp_zero.engines.browser import BrowserEngine
from linkedin_mcp_zero.engines.matching import MatchingEngine
from linkedin_mcp_zero.engines.resume import extract_resume_text
from linkedin_mcp_zero.scraping.guest_api import _extract_skills
from linkedin_mcp_zero.utils.circuit_breaker import CircuitBreaker


def test_csv_injection_sanitization(tmp_path: Path) -> None:
    """Ensure cell values starting with =, +, -, @, \\t are escaped with single quote."""
    mock_storage = AsyncMock()
    mock_storage.exports_dir = tmp_path
    mock_public = AsyncMock()
    mock_public.get_job_details.return_value = {
        "id": "100",
        "t": "=cmd|' /C calc'!A0",
        "co": "@malicious",
        "loc": "+Remote",
        "sal": "-$100k",
        "type": "\tFullTime",
        "url": "https://linkedin.com/jobs/view/100",
    }
    engine = MatchingEngine(mock_storage, mock_public)
    import asyncio

    res = asyncio.run(engine.export_jobs(["100"], fmt="csv"))
    assert Path(res["path"]).exists()
    content = Path(res["path"]).read_text(encoding="utf-8")
    assert "'=cmd" in content
    assert "'@malicious" in content
    assert "'+Remote" in content
    assert "'-$100k" in content


@pytest.mark.asyncio
async def test_browser_get_conversation_ssrf_protection() -> None:
    """Ensure get_conversation rejects non-linkedin domains."""
    mock_settings = AsyncMock()
    mock_settings.cdp_url = "http://localhost:9222"
    mock_settings.data_dir = None
    engine = BrowserEngine(mock_settings)

    with patch.object(engine, "_ensure_ready", return_value={"available": True}):
        res = await engine.get_conversation("http://attacker.com/steal-session")
        assert res.get("error") == "invalid_url"
        assert "linkedin.com" in res.get("detail", "")


def test_resume_pdf_missing_dependency_raises_import_error(tmp_path: Path) -> None:
    """Ensure extracting text from PDF without pymupdf raises ImportError instead of returning an error string."""
    fake_pdf = tmp_path / "resume.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    with patch.dict("sys.modules", {"fitz": None, "docling": None}):
        with pytest.raises(ImportError) as exc_info:
            extract_resume_text(fake_pdf, allowed_dirs=[tmp_path])
        assert "PDF support requires optional dependency" in str(exc_info.value)


def test_ttl_cache_thread_safety() -> None:
    """Ensure concurrent writes and reads to TTLCache do not raise RuntimeError or corrupt internal state."""
    cache: TTLCache[int] = TTLCache(ttl_seconds=60, max_entries=50)

    def worker(worker_id: int) -> None:
        for i in range(100):
            cache.set(f"key-{worker_id}-{i}", i)
            val = cache.get(f"key-{worker_id}-{i}")
            assert val is None or val == i

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, w) for w in range(8)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    assert cache.stats()["entries"] <= 50


def test_circuit_breaker_thread_safety() -> None:
    """Ensure concurrent failure recordings do not race on threshold."""
    cb = CircuitBreaker(failure_threshold=10, recovery_timeout=5.0)

    def worker() -> None:
        for _ in range(5):
            cb.record_failure()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker) for _ in range(4)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    assert cb.state == "OPEN"
    assert cb.failure_count == 20


def test_skill_extraction_word_boundary() -> None:
    """Ensure substrings like TRAINING do not falsely match AI."""
    text = "We provide comprehensive training and main programming in Python."
    skills = _extract_skills(text)
    assert "Python" in skills
    assert "AI" not in skills


def test_vector_storage_upsert_and_search() -> None:
    """Ensure VectorStorage indexes and searches with cosine similarity."""
    from linkedin_mcp_zero.storage import VectorStorage

    vs = VectorStorage(collection_name="test_resumes", vector_size=4)
    vs.upsert("doc1", [1.0, 0.0, 0.0, 0.0], {"title": "Python Dev"})
    vs.upsert("doc2", [0.0, 1.0, 0.0, 0.0], {"title": "Rust Dev"})

    results = vs.search([1.0, 0.1, 0.0, 0.0], limit=1)
    assert len(results) == 1
    assert results[0]["title"] == "Python Dev"
    assert results[0]["score"] > 0.9


def test_configurable_llm_provider_models() -> None:
    """Ensure LLMProvider respects configurable model parameters and environment variables."""
    import os

    from linkedin_mcp_zero.utils.llm import LLMProvider

    provider = LLMProvider(anthropic_model="custom-claude", openai_model="custom-gpt")
    assert provider.anthropic_model == "custom-claude"
    assert provider.openai_model == "custom-gpt"

    with patch.dict(
        os.environ,
        {
            "LINKEDIN_MCP_ANTHROPIC_MODEL": "env-claude",
            "LINKEDIN_MCP_OPENAI_MODEL": "env-gpt",
        },
    ):
        env_provider = LLMProvider()
        assert env_provider.anthropic_model == "env-claude"
        assert env_provider.openai_model == "env-gpt"


@pytest.mark.asyncio
async def test_guest_api_request_coalescing() -> None:
    """Ensure concurrent calls to get_job_details for the same job id coalesce into a single HTTP fetch."""
    import asyncio

    from linkedin_mcp_zero.scraping.guest_api import GuestAPIClient

    client = GuestAPIClient()
    mock_session = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><body><h1 class='top-card-layout__title'>Senior Engineer</h1></body></html>"

    async def slow_get(url: str) -> Any:
        await asyncio.sleep(0.05)
        return mock_resp

    mock_session.get.side_effect = slow_get

    with patch.object(client, "_get_session", return_value=mock_session):
        # Fire two concurrent calls for the same job_id
        task1 = asyncio.create_task(client.get_job_details("9999999"))
        task2 = asyncio.create_task(client.get_job_details("9999999"))
        res1, res2 = await asyncio.gather(task1, task2)

        assert res1 == res2
        # HTTP request should only have been made ONCE
        assert mock_session.get.call_count == 1


@pytest.mark.asyncio
async def test_health_check_database_validation(tmp_path: Path) -> None:
    """Ensure /health checks database connectivity and returns proper status."""
    from starlette.requests import Request

    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.server.app import create_app

    settings = Settings(data_dir=str(tmp_path))
    app = create_app(settings)

    # Call health route handler
    client_routes = [r for r in app._additional_http_routes if getattr(r, "path", None) == "/health"]
    assert len(client_routes) == 1
    health_endpoint = client_routes[0].endpoint

    mock_request = Request({"type": "http", "method": "GET", "path": "/health", "headers": []})
    resp = await health_endpoint(mock_request)
    import json

    data = json.loads(resp.body.decode("utf-8"))
    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_llm_provider_client_reuse() -> None:
    """Ensure LLMProvider reuses its httpx.AsyncClient instance across requests."""
    from linkedin_mcp_zero.utils.llm import LLMProvider

    provider = LLMProvider(api_key="test-key")
    client1 = await provider._get_client()
    client2 = await provider._get_client()
    assert client1 is client2
    await provider.close()
    assert provider._client is None


def test_fts5_indexing_and_bm25_search(tmp_path: Path) -> None:
    """Ensure Storage indexes job details into FTS5 and executes BM25 search."""
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(Settings(data_dir=str(tmp_path)))
    storage.index_job_fts(
        job_id="job_101",
        title="Senior Streaming Engineer",
        company="Stripe",
        location="Remote",
        description="High throughput Kafka and NATS distributed event pipelines.",
        skills="Kafka NATS Go",
    )
    storage.index_job_fts(
        job_id="job_102",
        title="Frontend React Developer",
        company="Vercel",
        location="San Francisco",
        description="Building user interfaces with Next.js and Tailwind.",
        skills="React TypeScript",
    )

    results = storage.search_jobs_fts("Kafka NATS", limit=5)
    assert len(results) >= 1
    assert results[0]["job_id"] == "job_101"
    assert "Streaming" in results[0]["title"]


def test_skill_graph_taxonomy_expansion(tmp_path: Path) -> None:
    """Ensure skill graph dynamically learns and expands technologies from real ingested data."""
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(Settings(data_dir=str(tmp_path)))
    # Dynamically record real skill co-occurrences as observed from real job postings or resumes
    storage.record_skill_cooccurrences(["kafka", "pub/sub", "message broker", "python"])
    storage.record_skill_cooccurrences(["docker", "containerization", "kubernetes", "cloud orchestration"])
    storage.record_skill_cooccurrences(["python", "asyncio", "fastapi"])

    expanded = storage.expand_skills(["kafka", "docker", "python"])

    assert "kafka" in expanded
    assert any("pub/sub" in s or "message broker" in s for s in expanded["kafka"])
    assert "docker" in expanded
    assert "containerization" in expanded["docker"]
    assert "python" in expanded
    assert "asyncio" in expanded["python"] or "fastapi" in expanded["python"]

    cluster = storage.get_skill_cluster("kubernetes")
    assert cluster["total_connections"] > 0
    assert any("cloud orchestration" in c.get("target_skill", "") for c in cluster["direct_connections"])


def test_job_viability_and_ghost_job_detection(tmp_path: Path) -> None:
    """Ensure evaluate_job_viability detects saturated applicant pools and reposted ghost jobs."""
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.engines.matching import MatchingEngine
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(Settings(data_dir=str(tmp_path)))
    mock_public = AsyncMock()
    engine = MatchingEngine(storage, mock_public)

    # Ghost job: Reposted 4 times, 500 applicants
    ghost_job = {
        "id": "ghost_1",
        "title": "Staff Python Engineer",
        "desc": "Reposted 4 times ago. Over 500 applicants submitted.",
    }
    viability = engine.evaluate_job_viability(ghost_job)
    assert viability["status"] == "GHOST_JOB_RISK"
    assert viability["viability_score"] < 0.4
    assert any("Reposted 4 times" in r for r in viability["risk_factors"])
    assert any("Hyper-saturated" in r for r in viability["risk_factors"])

    # Fresh active job: 0 reposts, 12 applicants
    fresh_job = {
        "id": "fresh_1",
        "title": "Backend Go Engineer",
        "desc": "Posted 10 hours ago. 12 applicants.",
    }
    fresh_viability = engine.evaluate_job_viability(fresh_job)
    assert fresh_viability["status"] == "ACTIVE_HIGH_PRIORITY"
    assert fresh_viability["viability_score"] >= 0.8


def test_reciprocal_rank_fusion_algorithm(tmp_path: Path) -> None:
    """Ensure RRF correctly fuses lexical BM25 and dense rank lists."""
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.engines.matching import MatchingEngine
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(Settings(data_dir=str(tmp_path)))
    engine = MatchingEngine(storage, AsyncMock())

    bm25_ranks = {"docA": 1, "docB": 2, "docC": 3}
    dense_ranks = {"docB": 1, "docA": 2, "docD": 3}

    rrf_scores = engine._reciprocal_rank_fusion(bm25_ranks, dense_ranks, k=60)
    top_doc = list(rrf_scores.keys())[0]
    # docA and docB appear in both lists and should score significantly higher than docC or docD
    assert top_doc in ("docA", "docB")
    assert rrf_scores["docC"] < rrf_scores["docA"]
    assert rrf_scores["docD"] < rrf_scores["docB"]


def test_empty_db_has_zero_preseeded_skills(tmp_path: Path) -> None:
    """Ensure a fresh database contains zero fake or pre-seeded data in skill_graph."""
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(Settings(data_dir=str(tmp_path)))
    with storage._connect() as conn:
        count = conn.execute("SELECT COUNT(*) as cnt FROM skill_graph").fetchone()["cnt"]
    assert count == 0


def test_save_resume_and_index_job_fts_auto_learn_skills(tmp_path: Path) -> None:
    """Ensure saving a resume or indexing a job dynamically teaches the skill graph in real time."""
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(Settings(data_dir=str(tmp_path)))

    # Save a resume with real extracted skills
    storage.save_resume("resume.txt", {"name": "Dev", "skills": ["Python", "FastAPI", "Docker"]})

    cluster = storage.get_skill_cluster("python")
    assert cluster["total_connections"] >= 2
    connected = [c["target_skill"] for c in cluster["direct_connections"]]
    assert "fastapi" in connected
    assert "docker" in connected

    # Index a job with skills string
    storage.index_job_fts(
        job_id="live_job_1",
        title="Systems Engineer",
        company="Acme",
        location="Remote",
        description="Rust microservices",
        skills="Rust Tokio Actix",
    )

    rust_cluster = storage.get_skill_cluster("rust")
    assert rust_cluster["total_connections"] >= 2
    rust_connected = [c["target_skill"] for c in rust_cluster["direct_connections"]]
    assert "tokio" in rust_connected
    assert "actix" in rust_connected


@pytest.mark.asyncio
async def test_analyze_job_viability_real_scraped_keys(tmp_path: Path) -> None:
    """Ensure analyze_job_viability accurately extracts metadata from real scraped job structures."""
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.engines.matching import MatchingEngine
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(Settings(data_dir=str(tmp_path)))
    mock_public = AsyncMock()
    mock_public.get_job_details.return_value = {
        "id": "real_999",
        "t": "Staff Distributed Systems Engineer",
        "co": "OpenAI",
        "loc": "San Francisco, CA",
        "desc": "Posted 2 hours ago. 5 applicants.",
    }
    engine = MatchingEngine(storage, mock_public)

    result = await engine.analyze_job_viability("real_999")
    assert result["title"] == "Staff Distributed Systems Engineer"
    assert result["company"] == "OpenAI"
    assert result["location"] == "San Francisco, CA"
    assert result["status"] == "ACTIVE_HIGH_PRIORITY"
    assert result["viability_score"] >= 0.8
