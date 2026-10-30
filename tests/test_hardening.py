"""Regression tests for the search-quality, skill-system and security fixes."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.config.skills import (
    canonicalize_skill,
    extract_skills_from_text,
    skill_gap,
)
from linkedin_mcp_zero.scraping import guest_api
from linkedin_mcp_zero.scraping.guest_api import (
    GuestAPIClient,
    NotFoundError,
    parse_search_results,
    polite_get,
    rank_by_title_relevance,
)
from linkedin_mcp_zero.server.middleware import APIKeyAndRateLimitMiddleware
from linkedin_mcp_zero.storage.db import Storage
from linkedin_mcp_zero.utils.errors import UpstreamError
from linkedin_mcp_zero.utils.oauth import OAuthMiddleware

# --------------------------------------------------------------------------- search


def _card(job_id: str, title: str, company: str) -> str:
    return (
        f'<li><div class="base-card job-search-card">'
        f'<a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/x-{job_id}?trk=1"></a>'
        f'<h3 class="base-search-card__title">{title}</h3>'
        f'<h4 class="base-search-card__subtitle">{company}</h4>'
        f'<span class="job-search-card__location">Madurai</span>'
        f'<time datetime="2026-10-20">3 days ago</time></div></li>'
    )


def test_parse_search_results_removes_duplicates() -> None:
    html = _card("4483635334", "Engineer", "A") + _card("4483635334", "Engineer", "A") + _card("4480089691", "X", "B")
    rows = parse_search_results(html)
    assert [r["id"] for r in rows] == ["4483635334", "4480089691"]


def test_rank_by_title_relevance_is_stable_and_never_drops() -> None:
    rows: list[dict[str, object]] = [
        {"id": "1", "t": "Lead Product Engineer"},
        {"id": "2", "t": "Technical Support Engineer"},
        {"id": "3", "t": "Support Engineer"},
    ]
    ranked = rank_by_title_relevance(rows, "technical support engineer")
    assert [r["id"] for r in ranked] == ["2", "3", "1"]
    assert len(ranked) == len(rows)


@pytest.mark.asyncio
async def test_company_name_filter_is_applied_client_side() -> None:
    client = GuestAPIClient()
    page = _card("111111", "Support Engineer", "Zoho") + _card("222222", "Support Engineer", "Qube Cinema")
    fake = MagicMock(status_code=200, text=page, headers={})
    seen_params: dict[str, Any] = {}

    async def fake_get(self: Any, url: str, params: dict[str, Any] | None = None) -> Any:
        seen_params.update(params or {})
        return fake

    with patch.object(guest_api, "polite_get", fake_get):
        rows = await client.search_jobs("support engineer", "Tamil Nadu", company="Zoho", limit=5)

    assert [r["co"] for r in rows] == ["Zoho"]
    assert "f_C" not in seen_params  # LinkedIn's f_C needs a numeric id, never a company name
    assert "Zoho" in str(seen_params["keywords"])


@pytest.mark.asyncio
async def test_numeric_company_id_uses_f_c() -> None:
    client = GuestAPIClient()
    seen: dict[str, Any] = {}

    async def fake_get(self: Any, url: str, params: dict[str, Any] | None = None) -> Any:
        seen.update(params or {})
        return MagicMock(status_code=200, text="", headers={})

    with patch.object(guest_api, "polite_get", fake_get):
        await client.search_jobs("engineer", company="1234")
    assert seen["f_C"] == "1234"


class _Resp:
    def __init__(self, status: int, headers: dict[str, str] | None = None) -> None:
        self.status_code = status
        self.headers = headers or {}
        self.text = ""


def _client_with(statuses: list[_Resp]) -> tuple[GuestAPIClient, MagicMock]:
    client = GuestAPIClient()
    session = MagicMock()
    session.get = AsyncMock(side_effect=statuses)
    client._session = session
    return client, session


@pytest.mark.asyncio
async def test_404_is_not_retried_and_does_not_trip_circuit_breaker() -> None:
    client, session = _client_with([_Resp(404)])
    with pytest.raises(NotFoundError):
        await polite_get(client, "https://example.test/x")
    assert session.get.await_count == 1
    assert client.circuit_breaker.failure_count == 0


@pytest.mark.asyncio
async def test_429_honors_retry_after_then_succeeds() -> None:
    client, session = _client_with([_Resp(429, {"Retry-After": "7"}), _Resp(200)])
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    with patch("linkedin_mcp_zero.scraping.guest_api.asyncio.sleep", fake_sleep):
        response = await polite_get(client, "https://example.test/x")
    assert response.status_code == 200
    assert sleeps == [7.0]
    assert session.get.await_count == 2


@pytest.mark.asyncio
async def test_403_fails_fast_without_hammering() -> None:
    client, session = _client_with([_Resp(403)])
    with pytest.raises(UpstreamError):
        await polite_get(client, "https://example.test/x")
    assert session.get.await_count == 1


def test_user_agent_is_stable_not_rotated() -> None:
    assert not hasattr(guest_api, "USER_AGENTS")


# --------------------------------------------------------------------------- skills


def test_alias_resolution_and_dedupe() -> None:
    found = extract_skills_from_text("Deployed on k8s with Postgres and golang; also Kubernetes and PostgreSQL.")
    assert found.count("Kubernetes") == 1
    assert found.count("PostgreSQL") == 1
    assert "Go" in found


def test_ambiguous_words_are_not_skills() -> None:
    assert extract_skills_from_text("I will go to the store, then run. Make it spring forward.") == []


def test_ambiguous_skill_in_skill_list_is_kept() -> None:
    found = extract_skills_from_text("Skills: Python, Go, R, SQL")
    assert {"Python", "Go", "R", "SQL"} <= set(found)


def test_it_support_domain_is_covered() -> None:
    text = "Help desk and desktop support: Windows 10, Active Directory, ticketing, ITIL, Zoho CRM, TeamViewer."
    found = set(extract_skills_from_text(text))
    assert {"Help Desk", "Desktop Support", "Active Directory", "Ticketing", "ITIL", "Zoho CRM", "TeamViewer"} <= found


def test_canonicalize_skill() -> None:
    assert canonicalize_skill("k8s") == "Kubernetes"
    assert canonicalize_skill("Google Cloud") == "GCP"
    assert canonicalize_skill("totally-unknown-tool") == "totally-unknown-tool"


def test_skill_gap_gives_transferable_credit() -> None:
    gap = skill_gap(
        ["Python", "Freshdesk"],
        ["Zendesk", "Python", "ITIL"],
        related={"zendesk": ["freshdesk"]},
    )
    assert gap["matched"] == ["Python"]
    assert gap["transferable"] == [{"need": "Zendesk", "have": "Freshdesk"}]
    assert gap["missing"] == ["ITIL"]
    assert gap["score"] == 0.5


def test_skill_cluster_works_on_fresh_install_without_fake_db_rows(tmp_path: Path) -> None:
    storage = Storage(Settings(data_dir=str(tmp_path)))
    cluster = storage.get_skill_cluster("k8s")
    assert cluster["canonical"] == "Kubernetes"
    assert any(r["skill"].lower() == "docker" for r in cluster["ranked_related"])
    with storage._connect() as conn:  # the project rule "no pre-seeded fake rows" still holds
        assert conn.execute("SELECT COUNT(*) AS c FROM skill_graph").fetchone()["c"] == 0


def test_fts_multiword_skills_are_split_on_commas(tmp_path: Path) -> None:
    storage = Storage(Settings(data_dir=str(tmp_path)))
    storage.index_job_fts("1", "Support", "Acme", "Madurai", "desc", skills="Help Desk, Active Directory")
    with storage._connect() as conn:
        rows = {r["source_skill"] for r in conn.execute("SELECT source_skill FROM skill_graph")}
    assert rows == {"help desk", "active directory"}


# --------------------------------------------------------------------------- security


async def _call(mw: Any, headers: list[tuple[bytes, bytes]], ip: str = "1.2.3.4") -> int:
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/mcp", "headers": headers, "client": (ip, 1)}
    await mw(scope, AsyncMock(), send)
    starts = [m for m in sent if m["type"] == "http.response.start"]
    return int(starts[0]["status"]) if starts else 200


@pytest.mark.asyncio
async def test_api_key_comparison_is_constant_time() -> None:
    mw = APIKeyAndRateLimitMiddleware(AsyncMock(), api_key="s3cret")
    with patch(
        "linkedin_mcp_zero.server.middleware.hmac.compare_digest", wraps=__import__("hmac").compare_digest
    ) as cd:
        assert await _call(mw, [(b"x-api-key", b"s3cret")]) == 200
    assert cd.called


@pytest.mark.asyncio
async def test_invalid_utf8_header_returns_401_not_500() -> None:
    mw = APIKeyAndRateLimitMiddleware(AsyncMock(), api_key="s3cret")
    assert await _call(mw, [(b"x-api-key", b"\xff\xfe")]) == 401


@pytest.mark.asyncio
async def test_brute_force_is_throttled_before_key_check() -> None:
    mw = APIKeyAndRateLimitMiddleware(AsyncMock(), api_key="s3cret")
    statuses = [await _call(mw, [(b"x-api-key", b"wrong")]) for _ in range(12)]
    assert statuses[:10] == [401] * 10
    assert statuses[10:] == [429, 429]
    # even the right key is refused during the lockout window
    assert await _call(mw, [(b"x-api-key", b"s3cret")]) == 429
    # a different client is unaffected
    assert await _call(mw, [(b"x-api-key", b"s3cret")], ip="9.9.9.9") == 200


def test_empty_api_key_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        APIKeyAndRateLimitMiddleware(AsyncMock(), api_key="")


@pytest.mark.asyncio
async def test_oauth_mode_skips_api_key_but_still_rate_limits() -> None:
    inner = AsyncMock()
    mw = APIKeyAndRateLimitMiddleware(inner, api_key=None, rate_limit_per_minute=2, require_api_key=False)
    assert await _call(mw, []) == 200
    assert await _call(mw, []) == 200
    assert await _call(mw, []) == 429


@pytest.mark.asyncio
async def test_oauth_rejects_request_without_token() -> None:
    inner = AsyncMock()
    settings = MagicMock(oauth_server_url="https://auth.example", oauth_client_id="a", oauth_client_secret="b")
    mw = OAuthMiddleware(inner, oauth_config=None, settings=settings)
    assert await _call(mw, []) == 401
    inner.assert_not_called()


def test_secrets_are_not_in_settings_repr() -> None:
    s = Settings(api_key="top-secret-key", anthropic_api_key="sk-ant-xyz", oauth_client_secret="shh")
    text = repr(s)
    assert "top-secret-key" not in text
    assert "sk-ant-xyz" not in text
    assert "shh" not in text


def test_safe_mode_blocks_account_automation_by_default() -> None:
    s = Settings(enable_browser=True, enable_voyager=True, enable_patchright_fallback=True, li_at="cookie")
    assert s.safe_mode is True
    assert not (s.enable_browser or s.enable_voyager or s.enable_patchright_fallback)
    assert s.li_at is None


def test_safe_mode_can_be_explicitly_disabled() -> None:
    s = Settings(enable_browser=True, safe_mode=False)
    assert s.enable_browser is True


def test_resume_rejects_hidden_files_and_huge_files(tmp_path: Path) -> None:
    from linkedin_mcp_zero.engines import resume

    hidden_dir = tmp_path / ".ssh"
    hidden_dir.mkdir()
    secret = hidden_dir / "notes.txt"
    secret.write_text("private")
    with pytest.raises(ValueError, match="hidden"):
        resume.extract_resume_text(str(secret), allowed_dirs=[tmp_path])

    big = tmp_path / "big.txt"
    big.write_bytes(b"a" * (resume.MAX_RESUME_BYTES + 1))
    with pytest.raises(ValueError, match="too large"):
        resume.extract_resume_text(str(big), allowed_dirs=[tmp_path])

    ok = tmp_path / "cv.txt"
    ok.write_text("Python developer")
    assert "Python" in resume.extract_resume_text(str(ok), allowed_dirs=[tmp_path])
