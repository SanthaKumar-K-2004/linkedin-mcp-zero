"""Regression tests for the hardening pass.

Each test maps to a bug found during a deep audit of the codebase; keep them
fast, hermetic, and free of network access.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from linkedin_mcp_zero.engines.matching import _csv_safe, _write_csv
from linkedin_mcp_zero.engines.multi_board import search_jobs_multi
from linkedin_mcp_zero.engines.resume import extract_resume_text
from linkedin_mcp_zero.scraping.guest_api import _parse_typeahead, parse_job_detail
from linkedin_mcp_zero.utils.salary import parse_min_salary, salary_meets_minimum
from linkedin_mcp_zero.utils.skills import match_skills


# --- stdout protocol safety (MCP stdio transport owns stdout) ----------------
def test_structlog_writes_to_stderr_only(capfd) -> None:
    # capfd (fd-level capture) is used deliberately: capsys would bind the
    # cached structlog logger to a capture object that gets closed after this
    # test, breaking later tests that log.
    import structlog

    from linkedin_mcp_zero.utils.logging import configure_logging

    configure_logging("INFO")
    structlog.get_logger().warning("protocol_safety_probe", marker="must_not_hit_stdout")
    captured = capfd.readouterr()
    assert "protocol_safety_probe" not in captured.out
    assert "protocol_safety_probe" in captured.err


def test_telemetry_exporter_targets_stderr() -> None:
    src = Path("src/linkedin_mcp_zero/utils/telemetry.py").read_text(encoding="utf-8")
    assert "ConsoleSpanExporter(out=sys.stderr)" in src


def test_trace_span_resolves_tracer_lazily() -> None:
    """trace_span must wrap even when decoration happens before init_telemetry."""
    from linkedin_mcp_zero.utils import telemetry

    @telemetry.trace_span("lazily.traced")
    async def probe() -> int:
        return 7

    # The function must be wrapped even before a tracer exists.
    assert hasattr(probe, "__wrapped__")

    class _Span:
        def __enter__(self) -> _Span:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    tracer = MagicMock()
    tracer.start_as_current_span.return_value = _Span()
    with patch.object(telemetry, "get_tracer", return_value=tracer):
        assert asyncio.run(probe()) == 7
        tracer.start_as_current_span.assert_called_once_with("lazily.traced")


# --- boundary-aware skill matching -------------------------------------------
def test_ai_skill_not_matched_inside_words() -> None:
    text = "Detail-oriented plumber. You maintain pipes and email daily availability reports."
    assert match_skills(text) == []


def test_ai_skill_matches_standalone_uppercase() -> None:
    assert "AI" in match_skills("Experience with AI/ML pipelines required.")


def test_skills_match_punctuation_terms() -> None:
    skills = match_skills("Strong C++ and Node.js background, plus C# and .NET.")
    for expected in ("C++", "Node.js", "C#", ".NET"):
        assert expected in skills


def test_skills_case_insensitive_for_longer_terms() -> None:
    assert "Python" in match_skills("expert in python and fastapi")


# --- salary parsing -----------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$120,000 - $150,000 a year", 120000),
        ("$150K-180K/yr", 150000),
        ("$95,000", 95000),
        ("95k a year", 95000),
    ],
)
def test_parse_min_salary(text: str, expected: int) -> None:
    assert parse_min_salary(text) == expected


def test_parse_min_salary_hourly_annualized() -> None:
    assert parse_min_salary("$45.00/hr") == 45 * 2080


def test_parse_min_salary_none_when_absent() -> None:
    assert parse_min_salary("Not disclosed") is None
    assert parse_min_salary("") is None


def test_salary_meets_minimum_truthful_cases() -> None:
    # The original bug: "$120,000 - $150,000" parsed as 120 and was rejected.
    assert salary_meets_minimum("$120,000 - $150,000 a year", 100000) is True
    assert salary_meets_minimum("$120K/yr", 130000) is False
    # unknown salary must not filter the job out
    assert salary_meets_minimum("", 200000) is True


# --- resume PDF handling -------------------------------------------------------
def test_pdf_without_pymupdf_raises_instead_of_returning_text(tmp_path: Path) -> None:
    fake_pdf = tmp_path / "resume.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    with patch.dict(sys.modules, {"fitz": None}), pytest.raises(ValueError, match="PDF support requires"):
        extract_resume_text(str(fake_pdf), allowed_dirs=[tmp_path])


# --- CSV export safety ---------------------------------------------------------
def test_csv_safe_defuses_formula_injection() -> None:
    assert _csv_safe("=cmd|'/c calc'!A1") == "'=cmd|'/c calc'!A1"
    assert _csv_safe("+1-800-evil") == "'+1-800-evil"
    assert _csv_safe("@SUM(1)") == "'@SUM(1)"
    assert _csv_safe("Normal Title") == "Normal Title"
    assert _csv_safe(123) == 123


def test_write_csv_escapes_malicious_cells(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    _write_csv(path, [{"id": "1", "t": '=HYPERLINK("http://evil")', "co": "Acme"}])
    content = path.read_text(encoding="utf-8")
    assert "'=HYPERLINK" in content


# --- multi-board search ---------------------------------------------------------
def test_search_jobs_multi_respects_limit_and_threads() -> None:
    rows = [
        {"title": f"Job {i}", "company": "Co", "location": "X", "site": "indeed", "job_url": "u"} for i in range(10)
    ]

    class _FakeFrame:
        def __init__(self, data: list[dict[str, Any]]) -> None:
            self._data = data

        def head(self, n: int) -> _FakeFrame:
            return _FakeFrame(self._data[:n])

        def iterrows(self):
            yield from enumerate(self._data)

    fake_scrape = MagicMock(return_value=_FakeFrame(rows))
    with patch.dict(sys.modules, {"jobspy": MagicMock(scrape_jobs=fake_scrape)}):
        result = asyncio.run(search_jobs_multi("python", "", limit=5, age=24))
    assert len(result) == 5  # previously returned limit * 5 rows
    fake_scrape.assert_called_once()


# --- geo id resolution ----------------------------------------------------------
def test_resolve_geo_id_numeric_passthrough_no_network() -> None:
    from linkedin_mcp_zero.scraping.guest_api import GuestAPIClient

    client = GuestAPIClient()
    assert asyncio.run(client.resolve_geo_id("103644278")) == "103644278"
    assert asyncio.run(client.resolve_geo_id("")) is None


def test_geo_typeahead_params_shape() -> None:
    from linkedin_mcp_zero.scraping.guest_api import GuestAPIClient

    client = GuestAPIClient()
    captured: dict[str, Any] = {}

    class _Resp:
        text = '{"hits": [{"geoId": 90000084, "name": "San Francisco Bay Area"}]}'

    async def fake_get(url: str, params: dict[str, Any], label: str) -> _Resp:
        captured.update(params)
        return _Resp()

    with patch.object(client, "_get", side_effect=fake_get):
        hits = asyncio.run(client.typeahead("san francisco", "GEO"))
    assert captured["typeaheadType"] == "GEO"
    assert captured["geoTypes"] == "POPULATED_PLACE"
    assert hits[0]["id"] == "90000084"


# --- xlsx export ------------------------------------------------------------------
def test_write_xlsx_valid_zip_and_injection_safe(tmp_path: Path) -> None:
    import xml.etree.ElementTree as ET
    import zipfile

    from linkedin_mcp_zero.engines.matching import _write_xlsx

    path = tmp_path / "jobs.xlsx"
    _write_xlsx(path, [{"id": "1", "t": "=EVIL()", "co": "Acme & Sons"}])
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        assert "[Content_Types].xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        sheet = archive.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet)  # must be well-formed XML
    assert root.tag.endswith("worksheet")
    text = sheet.decode("utf-8")
    assert "<f>" not in text and "<f " not in text  # no formula elements ever
    assert "&amp; Sons" in text  # XML escaping applied
    assert "=EVIL()" in text  # kept as literal inline string


# --- relative age future dates -----------------------------------------------------
def test_relative_age_future_date_is_clamped() -> None:
    from datetime import datetime, timedelta, timezone

    from linkedin_mcp_zero.utils.compress import relative_age

    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    future = (now + timedelta(days=2)).isoformat()
    assert relative_age(future, now) == "0h"


# --- typeahead parsing -----------------------------------------------------------
def test_parse_typeahead_company_shapes() -> None:
    body = json.dumps({"hits": [{"id": 1441, "name": "Google"}, {"urn": "urn:li:company:9999", "title": "Acme"}]})
    hits = _parse_typeahead(body, "COMPANY")
    by_name = {hit["name"]: hit["id"] for hit in hits}
    assert by_name["Google"] == "1441"
    assert by_name["Acme"] == "9999"


def test_parse_typeahead_garbage_returns_empty() -> None:
    assert _parse_typeahead("<html>not json</html>", "COMPANY") == []


# --- job detail applicants --------------------------------------------------------
def test_parse_job_detail_extracts_applicants() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting","title":"Dev","description":"Python"}
    </script>
    <figcaption class="num-applicants__caption">Over 200 applicants</figcaption>
    """
    detail = parse_job_detail(html, "123456")
    assert detail["appl"] == "200+"


# --- middleware timing-safe comparison ---------------------------------------------
def test_middleware_uses_constant_time_compare() -> None:
    src = Path("src/linkedin_mcp_zero/server/middleware.py").read_text(encoding="utf-8")
    assert "secrets.compare_digest" in src


# --- metrics retention --------------------------------------------------------------
def test_metrics_store_prunes_old_rows(tmp_path: Path) -> None:
    from linkedin_mcp_zero.config.settings import Settings
    from linkedin_mcp_zero.metrics.store import MetricsStore

    store = MetricsStore(Settings(data_dir=str(tmp_path), metrics_max_rows=100))
    for _ in range(150):
        store.insert_call(
            tool_name="probe",
            engine="test",
            called_at="2026-07-29T00:00:00Z",
            duration_ms=1,
            success=True,
            error_type=None,
            response_chars=4,
            response_bytes=4,
            tokens_estimated=1,
        )
    assert len(store.recent_calls(100)) == 100


# --- settings / env parsing ------------------------------------------------------
def test_cors_origins_accept_comma_separated_env(monkeypatch) -> None:
    from linkedin_mcp_zero.config.settings import Settings

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://a.example, https://b.example")
    settings = Settings()
    assert settings.cors_allowed_origins == ["http://a.example", "https://b.example"]


def test_cors_origins_accept_json_env(monkeypatch) -> None:
    from linkedin_mcp_zero.config.settings import Settings

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://only.example"]')
    settings = Settings()
    assert settings.cors_allowed_origins == ["http://only.example"]


def test_allowed_resume_dirs_comma_env(monkeypatch, tmp_path: Path) -> None:
    from linkedin_mcp_zero.config.settings import Settings

    first = tmp_path / "a"
    second = tmp_path / "cv"
    monkeypatch.setenv("LINKEDIN_MCP_ALLOWED_RESUME_DIRS", f"{first},{second}")
    settings = Settings()
    assert settings.allowed_resume_dirs == [str(first), str(second)]


# --- salary in description fallback -------------------------------------------------
@pytest.mark.parametrize(
    "snippet",
    [
        "$120,000 - $150,000 a year",
        "$120K-$150K",
        "$120K to $150K",
        "$45 - $55 per hour",
        "$45.00/hr",
    ],
)
def test_desc_salary_explicit_forms(snippet: str) -> None:
    from linkedin_mcp_zero.scraping.guest_api import _desc_salary

    assert _desc_salary(f"Great role! Compensation: {snippet}. Apply now.") != ""


def test_desc_salary_schema_preferred_over_desc() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting","title":"Dev","description":"x",
     "baseSalary":{"@type":"MonetaryAmount","currency":"USD",
     "value":{"@type":"QuantitativeValue","minValue":150000,"maxValue":200000,"unitText":"YEAR"}}}
    </script>
    """
    detail = parse_job_detail(html, "1")
    assert detail["sal"] == "$150K-200K/yr"
    assert detail["sal_src"] == "schema"


def test_desc_salary_fallback_marks_source() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting","title":"Dev",
     "description":"We pay $120K-$150K depending on experience."}
    </script>
    """
    detail = parse_job_detail(html, "1")
    assert detail["sal"] == "$120K-$150K"
    assert detail["sal_src"] == "desc"


def test_desc_salary_rejects_unrelated_money() -> None:
    from linkedin_mcp_zero.scraping.guest_api import _desc_salary

    assert _desc_salary("You will save the company $5,000 in equipment costs.") == ""


# --- distance param ------------------------------------------------------------------
def test_search_params_include_distance_and_geo() -> None:
    from linkedin_mcp_zero.scraping.guest_api import GuestAPIClient

    client = GuestAPIClient()
    captured: dict[str, Any] = {}

    class _Resp:
        text = ""

    async def fake_get(url: str, params: dict[str, Any], label: str) -> _Resp:
        captured.update(params)
        return _Resp()

    with patch.object(client, "_get", side_effect=fake_get):
        asyncio.run(client.search_jobs("dev", geo_id="90000084", distance=250, limit=5))
    assert captured["geoId"] == "90000084"
    assert captured["distance"] == "100"  # clamped


# --- doctor guest api probe ------------------------------------------------------------
def test_doctor_probe_disabled_by_default() -> None:
    from linkedin_mcp_zero.config.autodetect import detect_runtime

    runtime = detect_runtime(None, probe=False)
    assert runtime["guest_api"] is None


def test_probe_guest_api_handles_unreachable() -> None:
    import httpx

    from linkedin_mcp_zero.config import autodetect

    with patch.object(httpx, "Client", side_effect=httpx.ConnectError("nope")):
        assert autodetect._probe_guest_api().startswith("unreachable")


# --- salary source passthrough ------------------------------------------------------
def test_get_job_salary_preserves_sal_src() -> None:
    from linkedin_mcp_zero.config.settings import Settings as _S
    from linkedin_mcp_zero.engines.public_api import PublicAPIEngine

    engine = PublicAPIEngine(_S(data_dir=None))

    async def fake_details(job_id: str) -> dict[str, object]:
        return {"id": job_id, "sal": "$120K-$150K", "sal_src": "desc"}

    engine.get_job_details = fake_details  # type: ignore[method-assign]
    result = asyncio.run(engine.get_job_salary("42"))
    assert result["sal"] == "$120K-$150K"
    assert result["sal_src"] == "desc"


def test_multi_fallback_guest_client_gets_proxy() -> None:
    import linkedin_mcp_zero.engines.multi_board as mb

    captured: dict[str, Any] = {}

    class _FakeClient:
        def __init__(self, proxy: str | None = None, timeout: float = 15) -> None:
            captured["proxy"] = proxy

        async def search_jobs(self, **kwargs: Any) -> list[dict[str, Any]]:
            return [{"id": "1", "t": "x", "co": "y"}]

        async def close(self) -> None:
            return None

    with (
        patch.dict(sys.modules, {"jobspy": None}),
        patch.object(mb, "GuestAPIClient", _FakeClient),
    ):
        rows = asyncio.run(mb.search_jobs_multi("dev", "", 5, 168, proxy="http://127.0.0.1:8080"))
    assert captured["proxy"] == "http://127.0.0.1:8080"
    assert rows[0]["site"] == "linkedin"


# --- compact_location word boundaries -----------------------------------------
def test_compact_location_respects_word_boundaries() -> None:
    from linkedin_mcp_zero.utils.compress import compact_location

    # Substring replacement used to mangle these ("India" inside "Indiana",
    # "New York" inside "New Yorker").
    assert compact_location("Indianapolis, Indiana") == "Indianapolis, Indiana"
    assert compact_location("New Yorker Hotel, Newark") == "New Yorker Hotel, Newark"
    assert compact_location("New Yorkshire") == "New Yorkshire"
    # Real locations still compress (and compress fully).
    assert compact_location("San Francisco, California, United States") == "San Francisco, CA, US"
    assert compact_location("New York, New York") == "NY, NY"
    assert compact_location("Bengaluru, India") == "Bengaluru, IN"
    assert compact_location("Eindhoven, Netherlands") == "Eindhoven, NL"
    assert compact_location("Doncaster, United Kingdom") == "Doncaster, UK"
    # "Canada" is intentionally not mapped: "CA" is California in US listings,
    # so "Toronto, Canada" must never collapse into "Toronto, CA".
    assert compact_location("Toronto, Canada") == "Toronto, Canada"


# --- alert freq honoring -------------------------------------------------------
def test_alert_due_windows(tmp_path: Path) -> None:
    from linkedin_mcp_zero.config.settings import Settings as _S
    from linkedin_mcp_zero.storage.db import Storage

    storage = Storage(_S(data_dir=str(tmp_path)))
    daily = storage.save_alert("daily-probe", "python")
    weekly = storage.save_alert("weekly-probe", "rust", freq="weekly")

    # Never run -> always due.
    row = storage.selected_alerts([int(daily["id"])])[0]
    assert storage.alert_due(row) == (True, 0.0)

    # Just-run alerts are not due again inside their window.
    storage.update_alert_seen(int(daily["id"]), ["1"])
    storage.update_alert_seen(int(weekly["id"]), ["1"])
    daily_due, daily_wait = storage.alert_due(storage.selected_alerts([int(daily["id"])])[0])
    weekly_due, weekly_wait = storage.alert_due(storage.selected_alerts([int(weekly["id"])])[0])
    assert daily_due is False and 20 <= daily_wait < 24
    assert weekly_due is False and 24 < weekly_wait <= 168

    # Unknown freq values fall back to daily, never to run-forever.
    weird = dict(storage.selected_alerts([int(daily["id"])])[0])
    weird["freq"] = "hourly-typo"
    assert storage.alert_due(weird)[0] is False

    # Unparseable last_run_at must not silence the alert forever.
    row = dict(storage.selected_alerts([int(daily["id"])])[0])
    row["last_run_at"] = "not-a-date"
    assert storage.alert_due(row) == (True, 0.0)


def test_alert_last_run_at_migration(tmp_path: Path) -> None:
    import sqlite3

    from linkedin_mcp_zero.config.settings import Settings as _S
    from linkedin_mcp_zero.storage.db import Storage

    # Simulate a database created by an older release without last_run_at.
    (tmp_path / "state.sqlite3").touch()
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        conn.execute(
            "CREATE TABLE alerts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kw TEXT NOT NULL,"
            " loc TEXT DEFAULT '', freq TEXT DEFAULT 'daily', last_ids TEXT DEFAULT '[]',"
            " created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute("INSERT INTO alerts(name, kw) VALUES ('legacy', 'python')")

    storage = Storage(_S(data_dir=str(tmp_path)))
    listed = storage.list_alerts()
    assert listed[0]["last_run_at"] is None
    storage.update_alert_seen(1, ["1"])
    assert storage.selected_alerts([1])[0]["last_run_at"]


async def test_check_saved_alerts_honors_freq(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from linkedin_mcp_zero.config.settings import Settings as _S
    from linkedin_mcp_zero.engines.public_api import PublicAPIEngine
    from linkedin_mcp_zero.server.app import create_app

    calls: list[str] = []

    async def fake_search(self: Any, kw: str, **kwargs: Any) -> list[dict[str, Any]]:
        calls.append(kw)
        return [{"id": "1", "t": "x"}]

    monkeypatch.setattr(PublicAPIEngine, "search_jobs", fake_search)
    app = create_app(_S(data_dir=str(tmp_path)))
    await app.call_tool("save_job_alert", {"name": "n", "kw": "python"})

    # FastMCP wraps non-dict tool returns as {"result": [...]} in structured_content.
    def unwrap(sc: Any) -> list[dict[str, Any]]:
        return sc["result"] if isinstance(sc, dict) else sc

    # First scheduled run executes (never run -> due)...
    first = unwrap((await app.call_tool("check_saved_alerts", {})).structured_content)
    assert first[0]["new_matches"] == 1
    # ...an immediate second scheduled run is skipped as not due...
    second = unwrap((await app.call_tool("check_saved_alerts", {})).structured_content)
    assert second[0]["skipped"] == "not_due"
    assert second[0]["next_due_in_hours"] > 20
    # ...but passing the id explicitly forces a run.
    forced = unwrap((await app.call_tool("check_saved_alerts", {"ids": [1]})).structured_content)
    assert "skipped" not in forced[0]
    assert len(calls) == 2


# --- CLI --version ---------------------------------------------------------------
def test_cli_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    from linkedin_mcp_zero import __version__
    from linkedin_mcp_zero.main import build_parser

    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


# --- circuit breaker -----------------------------------------------------------
def test_circuit_breaker_half_open_single_probe() -> None:
    import time as _time

    from linkedin_mcp_zero.utils.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
    cb.record_failure()
    assert cb.state == "OPEN"

    _time.sleep(0.06)
    # Cooldown expired: exactly one probe is allowed through...
    assert cb.allow_request() is True
    assert cb.state == "HALF-OPEN"
    # ...a concurrent second request must NOT rush a still-unhealthy upstream.
    assert cb.allow_request() is False

    # A failed probe reopens the breaker immediately, with a fresh window.
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.allow_request() is False

    _time.sleep(0.06)
    assert cb.allow_request() is True
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb._probe_in_flight is False


async def test_circuit_breaker_ignores_4xx_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import linkedin_mcp_zero.scraping.guest_api as ga

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

    monkeypatch.setattr(ga, "AsyncRetrying", _NoWaitRetrying)

    class _Resp:
        def __init__(self, status: int) -> None:
            self.status_code = status

    class _Session:
        def __init__(self, status: int) -> None:
            self.status = status
            self.headers: dict[str, str] = {}

        async def get(self, url: str, params: dict[str, Any]) -> _Resp:
            return _Resp(self.status)

    # 404 (expired job id) is a request problem, not an upstream outage.
    client = ga.GuestAPIClient()
    client._session = _Session(404)
    with pytest.raises(ga.UpstreamError):
        await client._get("https://x", {}, "probe")
    assert client.circuit_breaker.failure_count == 0
    assert client.circuit_breaker.state == "CLOSED"

    # 429 means real rate limiting and must count.
    client._session = _Session(429)
    with pytest.raises(ga.UpstreamError):
        await client._get("https://x", {}, "probe")
    assert client.circuit_breaker.failure_count == 1


# --- exact-token background task retention --------------------------------------
async def test_exact_count_task_held_strongly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import linkedin_mcp_zero.metrics.tracking as tr
    from linkedin_mcp_zero.config.settings import Settings as _S
    from linkedin_mcp_zero.metrics.store import MetricsStore

    gate = asyncio.Event()

    async def slow_count(*args: Any, **kwargs: Any) -> None:
        await gate.wait()

    monkeypatch.setattr(tr, "_count_exact", slow_count)
    store = MetricsStore(_S(data_dir=str(tmp_path)))
    settings = _S(data_dir=str(tmp_path), exact_token_count=True, anthropic_api_key="k")

    before = len(tr._background_tasks)
    tr._record_call(store, settings, "tool.probe", "local", "now", 1, True, None, {"ok": True})
    assert len(tr._background_tasks) == before + 1  # not garbage-collectable

    gate.set()
    await asyncio.gather(*list(tr._background_tasks))
    await asyncio.sleep(0)
    assert len(tr._background_tasks) == before  # discarded on completion


# --- vector storage id determinism ------------------------------------------------
def test_vector_point_id_deterministic_and_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    import types
    import uuid

    from linkedin_mcp_zero.storage.vector_db import VectorStorage, _point_id

    a1, a2 = _point_id("resume_42"), _point_id("resume_42")
    assert a1 == a2  # stable across calls (hash() was process-random)
    uuid.UUID(a1)  # valid UUID accepted by Qdrant natively
    # Previously "resume_42" and "resume_100000042" collided after % 10**8.
    assert _point_id("resume_42") != _point_id("resume_100000042")

    class _PointStruct:
        def __init__(self, id: Any, vector: Any, payload: Any) -> None:
            self.id = id
            self.vector = vector
            self.payload = payload

    # qdrant-client is an optional extra and absent from the dev env; stub the
    # package and the models submodule so the deferred import inside upsert
    # resolves to our fake.
    qdrant_pkg = types.ModuleType("qdrant_client")
    qdrant_pkg.__path__ = []  # mark as package
    qdrant_models = types.ModuleType("qdrant_client.models")
    qdrant_models.PointStruct = _PointStruct  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_pkg)
    monkeypatch.setitem(sys.modules, "qdrant_client.models", qdrant_models)

    class _FakeClient:
        def __init__(self) -> None:
            self.points: list[Any] = []

        def upsert(self, collection_name: str, points: list[Any]) -> None:
            self.points.extend(points)

    vs = VectorStorage()
    fake = _FakeClient()
    vs.client = fake  # type: ignore[assignment]
    vs.upsert("resume_42", [0.1, 0.2], {"path": "x"})
    assert fake.points[0].id == _point_id("resume_42")
    assert fake.points[0].payload["doc_id"] == "resume_42"


# --- job criteria extraction -------------------------------------------------------
_CRITERIA_HTML = """<html><head><script type="application/ld+json">
{"@type": "JobPosting", "title": "DevOps Engineer", "datePosted": "2026-07-20",
 "hiringOrganization": {"name": "Acme"},
 "jobLocation": {"address": {"addressLocality": "Berlin", "addressCountry": "Germany"}}}
</script></head><body>
<ul class="description__job-criteria-list">
 <li class="description__job-criteria-item"><h3>Seniority level</h3><span>Mid-Senior level</span></li>
 <li class="description__job-criteria-item"><h3>Employment type</h3><span>Full-time</span></li>
 <li class="description__job-criteria-item"><h3>Job function</h3><span>Engineering</span></li>
 <li class="description__job-criteria-item"><h3>Industries</h3><span>Software Development</span></li>
</ul></body></html>"""


def test_parse_job_detail_extracts_criteria() -> None:
    result = parse_job_detail(_CRITERIA_HTML, "99")
    assert result["cr"] == {"sen": "Mid-Senior level", "func": "Engineering", "ind": "Software Development"}
    # Employment type came from the criteria list (schema had none).
    assert result["type"] == "FT"
    assert "etype" not in result["cr"]


def test_employment_type_handles_none_and_hyphenated() -> None:
    from linkedin_mcp_zero.scraping.guest_api import _employment_type

    # Absent type must stay absent — it used to leak the literal "NONE".
    assert _employment_type(None) == ""
    assert _employment_type("FULL_TIME") == "FT"
    assert _employment_type("Full-time") == "FT"
    assert _employment_type("Part Time") == "PT"
