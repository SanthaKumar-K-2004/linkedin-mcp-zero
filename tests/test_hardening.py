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
