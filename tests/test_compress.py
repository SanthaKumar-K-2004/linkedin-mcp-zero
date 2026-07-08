from datetime import datetime, timezone

from hypothesis import given
from hypothesis import strategies as st

from linkedin_mcp_zero.utils.compress import (
    clean_text,
    compact_dict,
    compact_location,
    relative_age,
    truncate,
)


@given(st.text())
def test_clean_text_never_has_double_spaces(text: str) -> None:
    result = clean_text(text)
    assert "  " not in result


@given(st.text(min_size=1, max_size=1000), st.integers(min_value=1, max_value=500))
def test_truncate_respects_max_chars(text: str, max_chars: int) -> None:
    result = truncate(text, max_chars)
    assert len(result) <= max_chars + 3  # +3 for "..."


def test_clean_text_none() -> None:
    assert clean_text(None) == ""


def test_clean_text_unescape() -> None:
    assert clean_text("Python &amp; Java") == "Python & Java"


def test_truncate_short() -> None:
    assert truncate("Python", 10) == "Python"
    assert truncate(None, 10) == ""


def test_compact_dict_removes_empty() -> None:
    assert compact_dict({"a": "x", "b": "", "c": None, "d": [], "e": 0}) == {"a": "x", "e": 0}


def test_compact_location() -> None:
    assert compact_location("New York, United States") == "NY, US"
    assert compact_location("California, United Kingdom") == "CA, UK"
    assert compact_location(None) == ""


def test_relative_age_text() -> None:
    assert relative_age("2 hours ago") == "2 h"
    assert relative_age("3 days ago") == "3 d"
    assert relative_age("1 week ago") == "1 w"
    assert relative_age("2 months ago") == "2 mo"
    assert relative_age("1 year ago") == "1 y"
    assert relative_age(None) == ""


def test_relative_age_iso() -> None:
    now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
    # 2 hours ago
    assert relative_age("2026-07-08T10:00:00Z", now=now) == "2h"
    # 3 days ago
    assert relative_age("2026-07-05T12:00:00Z", now=now) == "3d"
    # 2 weeks ago
    assert relative_age("2026-06-24T12:00:00Z", now=now) == "2w"
    # 1 month ago
    assert relative_age("2026-06-08T12:00:00Z", now=now) == "1mo"


def test_relative_age_invalid_iso() -> None:
    assert relative_age("not-a-date") == "not-a-date"
