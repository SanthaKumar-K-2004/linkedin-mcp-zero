"""Behavioral tests for PublicAPIEngine — the thinnest-covered critical path.

These tests pin caching, company/geo resolution wiring, honest fallbacks, and
the aggregation helpers without any network access.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.engines.public_api import (
    PublicAPIEngine,
    _remote_pct,
    _top_counts,
    compact_company_profile,
)
from linkedin_mcp_zero.utils.errors import UpstreamError


class FakeGuestClient:
    """Canned stand-in for GuestAPIClient with call recording."""

    def __init__(self) -> None:
        self.search_calls: list[dict[str, Any]] = []
        self.detail_calls: list[str] = []
        self.typeahead_calls: list[tuple[str, str]] = []
        self.search_result: list[dict[str, Any]] = []
        self.typeahead_hits: list[dict[str, str]] = []
        self.company_ids: dict[str, str | None] = {}
        self.geo_ids: dict[str, str | None] = {}
        self.details: dict[str, dict[str, Any] | Exception] = {}

    async def close(self) -> None:
        return None

    async def search_jobs(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.search_calls.append(kwargs)
        return list(self.search_result)

    async def get_job_details(self, job_id: str) -> dict[str, Any]:
        self.detail_calls.append(job_id)
        value = self.details.get(job_id, {"id": job_id})
        if isinstance(value, Exception):
            raise value
        return value

    async def resolve_company_id(self, name: str) -> str | None:
        return self.company_ids.get(name.strip().lower())

    async def resolve_geo_id(self, place: str) -> str | None:
        return self.geo_ids.get(place.strip().lower())

    async def typeahead(self, query: str, kind: str = "COMPANY") -> list[dict[str, str]]:
        self.typeahead_calls.append((query, kind))
        return list(self.typeahead_hits)


class _NoWaitBucket:
    async def acquire(self) -> None:
        return None


def make_engine(client: FakeGuestClient | None = None) -> tuple[PublicAPIEngine, FakeGuestClient]:
    client = client or FakeGuestClient()
    engine = PublicAPIEngine(Settings(data_dir=None))
    engine.client = client  # type: ignore[assignment]
    engine.bucket = _NoWaitBucket()  # type: ignore[assignment]
    return engine, client


# --- caching ----------------------------------------------------------------------
async def test_search_jobs_serves_from_cache() -> None:
    engine, client = make_engine()
    client.search_result = [{"id": "1", "t": "Eng"}]

    first = await engine.search_jobs("python")
    second = await engine.search_jobs("python")
    assert first == second
    assert len(client.search_calls) == 1  # second call was a cache hit

    # A different parameter set must not be served stale results.
    await engine.search_jobs("python", loc="remote")
    assert len(client.search_calls) == 2


async def test_get_job_details_serves_from_cache() -> None:
    engine, client = make_engine()
    client.details["9"] = {"id": "9", "sal": "$100K"}
    assert (await engine.get_job_details("9"))["sal"] == "$100K"
    await engine.get_job_details("9")
    assert client.detail_calls == ["9"]


# --- advanced search resolution wiring ---------------------------------------------
async def test_advanced_search_resolves_company_and_geo() -> None:
    engine, client = make_engine()
    client.company_ids["acme"] = "1441"
    client.geo_ids["berlin"] = "106974809"
    client.search_result = [{"id": "1"}]

    await engine.search_jobs_advanced("dev", co="Acme", geo="Berlin", distance=25)
    call = client.search_calls[0]
    assert call["company_id"] == "1441"
    assert call["geo_id"] == "106974809"
    assert call["distance"] == 25


async def test_advanced_search_unresolved_company_falls_back_to_honest_filter() -> None:
    engine, client = make_engine()
    client.company_ids["acme"] = None  # typeahead outage/unresolvable
    client.search_result = [
        {"id": "1", "co": "Acme Corp"},
        {"id": "2", "co": "Other Inc"},
    ]
    result = await engine.search_jobs_advanced("dev", co="acme")
    # Results remain truthful: only jobs actually at the named company.
    assert [row["id"] for row in result] == ["1"]
    assert client.search_calls[0]["company_id"] == ""


# --- company tools --------------------------------------------------------------------
async def test_get_company_jobs_prefers_resolved_id() -> None:
    engine, client = make_engine()
    client.company_ids["acme"] = "1441"
    client.search_result = [{"id": "1"}]
    result = await engine.get_company_jobs("Acme", loc="remote")
    assert client.search_calls[0] == {"kw": "", "loc": "remote", "company_id": "1441", "limit": 10}
    assert result == [{"id": "1"}]
    await engine.get_company_jobs("Acme", loc="remote")
    assert len(client.search_calls) == 1  # cached on second call


async def test_get_company_jobs_name_fallback_filters() -> None:
    engine, client = make_engine()
    client.company_ids["acme"] = None
    client.search_result = [{"id": "1", "co": "Acme Corp"}, {"id": "2", "co": "Other"}]
    result = await engine.get_company_jobs("Acme")
    assert [row["id"] for row in result] == ["1"]


async def test_search_companies_typeahead_path() -> None:
    engine, client = make_engine()
    client.typeahead_hits = [
        {"id": "1441", "name": "Microsoft"},
        {"id": "1035", "name": "Microsoft Research"},
    ]
    result = await engine.search_companies("microsoft", limit=1)
    assert result == [{"name": "Microsoft", "company_id": "1441", "source": "linkedin_typeahead"}]


async def test_search_companies_jobs_fallback_aggregates() -> None:
    engine, client = make_engine()
    client.typeahead_hits = []
    client.search_result = [
        {"id": "1", "co": "Acme", "t": "Dev"},
        {"id": "2", "co": "acme", "t": "Ops"},  # same company, different case
        {"id": "3", "co": "", "t": "Skip"},  # ignored: no company
    ]
    result = await engine.search_companies("dev")
    assert len(result) == 1
    row = result[0]
    assert row["name"] == "Acme"
    assert row["open_jobs"] == 2
    assert row["sample_roles"] == ["Dev", "Ops"]


async def test_get_company_profile_shape() -> None:
    engine, client = make_engine()
    client.company_ids["acme"] = "1441"
    client.search_result = [
        {"id": "1", "t": "Dev", "loc": "Berlin, DE"},
        {"id": "2", "t": "Ops", "loc": "Austin, US"},
    ]
    profile = await engine.get_company_profile("Acme")
    assert profile["company_id"] == "1441"
    assert profile["loc"] == ["Austin, US", "Berlin, DE"]  # sorted
    assert profile["open_jobs_seen"] == 2
    assert profile["source"] == "public_jobs_inference"


# --- aggregations -----------------------------------------------------------------------
async def test_get_job_trends_aggregates() -> None:
    engine, client = make_engine()
    client.search_result = [
        {"id": "1", "co": "Acme", "loc": "Remote"},
        {"id": "2", "co": "Acme", "loc": "Berlin, DE"},
        {"id": "3", "co": "Other", "loc": "Remote"},
    ]
    trends = await engine.get_job_trends("python", "remote")
    assert trends["sample"] == 3
    assert trends["top_companies"][0] == {"name": "Acme", "count": 2}
    assert trends["top_locations"][0] == {"name": "Remote", "count": 2}
    assert trends["remote_pct"] == 67


async def test_get_industry_insights_tallies_skills_and_survives_failures() -> None:
    engine, client = make_engine()
    client.search_result = [{"id": "1", "t": "Dev"}, {"id": "2", "t": "Dev"}, {"id": "3", "t": "Ops"}]
    client.details = {
        "1": {"id": "1", "skills": ["Python", "Docker"]},
        "2": {"id": "2", "skills": ["Python"]},
        "3": UpstreamError("boom"),  # a failing detail must not sink the tool
    }
    insights = await engine.get_industry_insights("python")
    assert insights["top_roles"][0] == {"name": "Dev", "count": 2}
    assert insights["in_demand_skills"] == ["Python", "Docker"]


def test_helpers() -> None:
    assert _top_counts({"b": 2, "a": 3, "c": 1}, limit=2) == [
        {"name": "a", "count": 3},
        {"name": "b", "count": 2},
    ]
    assert _remote_pct([]) == 0
    assert _remote_pct([{"loc": "Remote"}, {"loc": "Austin, US"}, {"loc": "remote"}]) == 67
    assert compact_company_profile({"a": 1, "b": "", "c": [], "d": None}) == {"a": 1}


# --- pagination dedupe in the guest client ------------------------------------------------
def _card(job_id: int) -> str:
    return (
        f'<div class="base-card"><h3 class="base-search-card__title">Eng {job_id}</h3>'
        f'<h4 class="base-search-card__subtitle">Acme</h4>'
        f'<a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/{job_id}"></a></div>'
    )


class _NoWaitRetrying:
    def __init__(self, **kwargs: Any) -> None:
        pass

    async def __aiter__(self) -> Any:
        for _ in range(3):
            yield self

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


async def test_pagination_dedupes_across_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    import linkedin_mcp_zero.scraping.guest_api as ga

    monkeypatch.setattr(ga, "AsyncRetrying", _NoWaitRetrying)

    class _Resp:
        def __init__(self, text: str) -> None:
            self.text = text
            self.status_code = 200

    class _Session:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}
            self.starts: list[int] = []
            # Page 2 overlaps page 1 (live re-ranking shifted job 3 down);
            # page 3 is entirely repeats, signalling window exhaustion.
            self.pages = {
                0: "".join(_card(i) for i in (400000001, 400000002, 400000003)),
                3: "".join(_card(i) for i in (400000003, 400000004, 400000005)),
                6: "".join(_card(i) for i in (400000001, 400000002)),
            }

        async def get(self, url: str, params: dict[str, Any]) -> _Resp:
            start = int(params["start"])
            self.starts.append(start)
            return _Resp(self.pages.get(start, ""))

    client = ga.GuestAPIClient()
    session = _Session()
    client._session = session  # type: ignore[assignment]
    rows = await client.search_jobs("dev", limit=10)
    assert [row["id"] for row in rows] == ["400000001", "400000002", "400000003", "400000004", "400000005"]
    assert session.starts == [0, 3, 6]  # advanced by actual page size


# --- CLI surface ---------------------------------------------------------------------------
def test_cli_doctor_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    import linkedin_mcp_zero.main as main_mod

    monkeypatch.setattr(sys, "argv", ["prog", "--doctor", "--json"])
    monkeypatch.setattr(
        main_mod, "detect_runtime", lambda data_dir, probe=False: {"os": "test-os", "guest_api": "unreachable"}
    )
    main_mod.cli()
    out = json.loads(capsys.readouterr().out)
    assert out == {"os": "test-os", "guest_api": "unreachable"}


def test_cli_print_config(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    import linkedin_mcp_zero.main as main_mod

    monkeypatch.setattr(sys, "argv", ["prog", "--print-config"])
    main_mod.cli()
    out = json.loads(capsys.readouterr().out)
    assert "mcpServers" in out
    servers = out["mcpServers"]
    assert len(servers) == 1
    assert servers[next(iter(servers))]["command"] == "uvx"


def test_malformed_card_url_does_not_kill_page_parse() -> None:
    from linkedin_mcp_zero.scraping.guest_api import parse_search_results

    bad = (
        '<div class="base-card"><h3 class="base-search-card__title">Weird</h3>'
        '<a class="base-card__full-link" href="/jobs/view/not-a-real-url"></a></div>'
    )
    rows = parse_search_results(bad + _card(400000042))
    # The good card survives one malformed neighbour; the bad row stays id-less.
    by_id = {row.get("id", ""): row for row in rows}
    assert "400000042" in by_id
    assert "" in by_id
