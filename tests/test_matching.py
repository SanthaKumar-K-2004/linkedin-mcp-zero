from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.engines.matching import MatchingEngine
from linkedin_mcp_zero.engines.public_api import PublicAPIEngine
from linkedin_mcp_zero.storage.db import Storage


@pytest.fixture
def mock_dependencies(tmp_path) -> tuple[Storage, PublicAPIEngine]:
    settings = Settings(data_dir=str(tmp_path))
    storage = Storage(settings)
    public = MagicMock(spec=PublicAPIEngine)
    return storage, public


def test_semantic_score_tfidf_fallback(mock_dependencies) -> None:
    storage, public = mock_dependencies
    engine = MatchingEngine(storage, public)

    score_same = engine._semantic_score("python software engineer", "python software engineer")
    assert score_same > 0.99

    score_diff = engine._semantic_score("python software engineer", "gardening flowers")
    assert score_diff < 0.2


@pytest.mark.asyncio
async def test_match_jobs_to_resume(mock_dependencies) -> None:
    storage, public = mock_dependencies

    # Save a resume
    resume_id = storage.save_resume(
        "/dummy/path",
        {
            "name": "Jane",
            "skills": ["python", "docker"],
        },
    )

    # Mock search jobs returning job postings
    public.search_jobs = AsyncMock(
        return_value=[{"id": "1", "t": "Python Dev", "co": "Google", "loc": "NY", "url": "url1"}]
    )
    public.get_job_details = AsyncMock(
        return_value={
            "id": "1",
            "t": "Python Dev",
            "desc": "Looking for python and docker engineers.",
            "skills": ["python", "docker"],
        }
    )

    engine = MatchingEngine(storage, public)
    res = await engine.match_jobs_to_resume(resume_id, min_score=30)

    assert "matches" in res
    assert len(res["matches"]) == 1
    assert res["matches"][0]["id"] == "1"
    assert res["matches"][0]["score"] > 30


@pytest.mark.asyncio
async def test_match_jobs_to_resume_not_found(mock_dependencies) -> None:
    storage, public = mock_dependencies
    engine = MatchingEngine(storage, public)
    res = await engine.match_jobs_to_resume(999)
    assert res["error"] == "resume_not_found"


@pytest.mark.asyncio
async def test_compare_jobs(mock_dependencies) -> None:
    storage, public = mock_dependencies

    public.get_job_details = AsyncMock(
        side_effect=[
            {"co": "Google", "t": "Python Dev", "sal": "$150K", "loc": "NY", "type": "FT", "url": "url1"},
            Exception("Failed to fetch"),
        ]
    )

    engine = MatchingEngine(storage, public)
    res = await engine.compare_jobs(["1", "2"])

    assert len(res["rows"]) == 2
    assert res["rows"][0] == ["Google", "Python Dev", "$150K", "NY", "FT", "url1"]
    assert res["rows"][1][0] == "ERROR"


@pytest.mark.asyncio
async def test_export_jobs_json(mock_dependencies, tmp_path) -> None:
    storage, public = mock_dependencies
    storage.exports_dir = tmp_path / "exports"
    storage.exports_dir.mkdir(parents=True, exist_ok=True)

    public.get_job_details = AsyncMock(return_value={"co": "Google", "t": "Python Dev", "sal": "$150K", "loc": "NY"})

    engine = MatchingEngine(storage, public)
    res = await engine.export_jobs(["1"], fmt="json")

    assert res["fmt"] == "json"
    assert res["count"] == 1
    assert Path(res["path"]).exists()
    assert '"Google"' in Path(res["path"]).read_text()


@pytest.mark.asyncio
async def test_export_jobs_csv(mock_dependencies, tmp_path) -> None:
    storage, public = mock_dependencies
    storage.exports_dir = tmp_path / "exports"
    storage.exports_dir.mkdir(parents=True, exist_ok=True)

    public.get_job_details = AsyncMock(
        return_value={
            "co": "Google",
            "t": "Python Dev",
            "sal": "$150K",
            "loc": "NY",
            "id": "1",
            "url": "url1",
            "type": "FT",
        }
    )

    engine = MatchingEngine(storage, public)
    res = await engine.export_jobs(["1"], fmt="csv")

    assert res["fmt"] == "csv"
    assert res["count"] == 1
    assert Path(res["path"]).exists()
    content = Path(res["path"]).read_text()
    assert "Google" in content
    assert "Python Dev" in content


@pytest.mark.asyncio
async def test_export_jobs_xlsx_unsupported(mock_dependencies) -> None:
    storage, public = mock_dependencies
    engine = MatchingEngine(storage, public)
    res = await engine.export_jobs(["1"], fmt="xlsx")
    assert "error" in res
    assert res["error"] == "xlsx_not_enabled"
