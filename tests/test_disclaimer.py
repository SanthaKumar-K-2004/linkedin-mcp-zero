from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from linkedin_mcp_zero.server.disclaimer import show_disclaimer_if_needed


def test_disclaimer_first_run_creates_file(tmp_path: Path) -> None:
    disclaimer_file = tmp_path / "disclaimer_accepted.txt"
    assert not disclaimer_file.exists()

    with patch("rich.console.Console.print") as mock_print:
        show_disclaimer_if_needed(tmp_path)
        mock_print.assert_called_once()
        assert disclaimer_file.exists()
        assert disclaimer_file.read_text(encoding="utf-8") == "Accepted"


def test_disclaimer_subsequent_runs_suppress_notice(tmp_path: Path) -> None:
    disclaimer_file = tmp_path / "disclaimer_accepted.txt"
    disclaimer_file.write_text("Accepted", encoding="utf-8")

    with patch("rich.console.Console.print") as mock_print:
        show_disclaimer_if_needed(tmp_path)
        mock_print.assert_not_called()
