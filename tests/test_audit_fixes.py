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


@pytest.mark.asyncio
async def test_export_jobs_custom_filename_and_path_traversal(tmp_path: Path) -> None:
    """Ensure custom filename is supported and directory traversal attempts are sanitized or rejected."""
    mock_storage = AsyncMock()
    mock_storage.exports_dir = tmp_path
    mock_public = AsyncMock()
    mock_public.get_job_details.return_value = {
        "id": "201",
        "company": "DeepMind",
        "title": "Research Scientist",
        "location": "London, UK",
        "salary": "£180k",
        "job_type": "Full-time",
        "url": "https://linkedin.com/jobs/view/201",
    }
    engine = MatchingEngine(mock_storage, mock_public)

    # 1. Custom filename creates file with proper extension
    res = await engine.export_jobs(["201"], fmt="json", filename="deepmind_roles")
    assert res["count"] == 1
    assert "deepmind_roles.json" in res["path"]
    assert Path(res["path"]).exists()
    content = Path(res["path"]).read_text(encoding="utf-8")
    assert "DeepMind" in content

    # 2. Path traversal attempt like "../../evil" is stripped to basename and contained inside exports_dir
    res_traversal = await engine.export_jobs(["201"], fmt="csv", filename="../../evil_export")
    assert res_traversal["count"] == 1
    target_path = Path(res_traversal["path"])
    assert target_path.parent == tmp_path
    assert target_path.name == "evil_export.csv"


@pytest.mark.asyncio
async def test_export_jobs_and_compare_jobs_field_aliases(tmp_path: Path) -> None:
    """Ensure compare_jobs and export_jobs handle alternate field names like company/title/salary/location."""
    mock_storage = AsyncMock()
    mock_storage.exports_dir = tmp_path
    mock_public = AsyncMock()
    mock_public.get_job_details.return_value = {
        "id": "301",
        "company": "Anthropic",
        "title": "Safety Researcher",
        "salary": "$250k",
        "location": "San Francisco, CA",
        "job_type": "Full-time",
        "url": "https://linkedin.com/jobs/view/301",
    }
    engine = MatchingEngine(mock_storage, mock_public)

    # Verify compare_jobs populates row correctly
    comp = await engine.compare_jobs(["301"])
    assert len(comp["rows"]) == 1
    row = comp["rows"][0]
    assert row[0] == "Anthropic"
    assert row[1] == "Safety Researcher"
    assert row[2] == "$250k"
    assert row[3] == "San Francisco, CA"
    assert row[4] == "Full-time"

    # Verify export_jobs CSV sanitizes and writes all aliased fields
    res_csv = await engine.export_jobs(["301"], fmt="csv")
    csv_text = Path(res_csv["path"]).read_text(encoding="utf-8")
    assert "Anthropic" in csv_text
    assert "Safety Researcher" in csv_text
    assert "$250k" in csv_text


def test_storage_skill_graph_none_and_invalid_type_resilience(tmp_path: Path) -> None:
    """Ensure Storage skill graph methods gracefully handle None, non-string, and empty skill inputs."""
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(Settings(data_dir=str(tmp_path)))

    # record_skill_cooccurrences with non-string, None, empty entries
    storage.record_skill_cooccurrences(["Python", None, 123, "   ", "Docker"])  # type: ignore[list-item]

    # expand_skills with None / invalid values
    taxonomy = storage.expand_skills(["Python", None, 456])  # type: ignore[list-item]
    assert "Python" in taxonomy
    assert taxonomy["Python"] == ["docker"]

    # get_skill_cluster with None or invalid values
    empty_cluster = storage.get_skill_cluster(None)  # type: ignore[arg-type]
    assert empty_cluster["total_connections"] == 0
    assert empty_cluster["direct_connections"] == []


def test_version_consistency_and_catalog_synchronization() -> None:
    """Ensure __version__ matches v0.4.0 and all 44 tools are registered in catalog."""
    import linkedin_mcp_zero
    from linkedin_mcp_zero.server.catalog import TOOLS, tool_help

    assert linkedin_mcp_zero.__version__ == "0.4.2"
    assert len(TOOLS) == 44
    assert tool_help("dia")["name"] == "deep_industry_analysis"


def test_metrics_store_connection_timeout_and_permissions(tmp_path: Path) -> None:
    """Ensure MetricsStore initializes with WAL, busy_timeout, and chmod 0600 security."""
    import stat

    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.metrics.store import MetricsStore

    settings = Settings(data_dir=str(tmp_path))
    store = MetricsStore(settings)

    # Check connection PRAGMA busy_timeout
    with store._connect() as conn:
        timeout_row = conn.execute("PRAGMA busy_timeout").fetchone()
        assert timeout_row[0] == 5000

    # Check file permissions on metrics.sqlite3
    mode = stat.S_IMODE(store.db_path.stat().st_mode)
    assert mode == 0o600


def test_vector_storage_uuid5_upsert_and_fallback(tmp_path: Path) -> None:
    """Ensure VectorStorage handles arbitrary string doc_ids without collisions."""
    from linkedin_mcp_zero.storage.vector_db import VectorStorage

    store = VectorStorage(collection_name="test_col")
    store.upsert("doc_alpha_123", [0.1, 0.2, 0.3], {"title": "Engineer"})
    store.upsert("doc_beta_456", [0.9, 0.8, 0.7], {"title": "Scientist"})

    results = store.search([0.9, 0.8, 0.7], limit=1)
    assert len(results) == 1
    assert results[0]["title"] == "Scientist"
