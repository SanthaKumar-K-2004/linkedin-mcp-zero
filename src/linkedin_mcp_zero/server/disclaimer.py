from __future__ import annotations

from pathlib import Path

from rich.console import Console

DISCLAIMER_TEXT = """
[bold red]================================================================================[/bold red]
[bold yellow]⚠️  SAFE USE NOTICE & DISCLAIMER:[/bold yellow]
This tool (linkedin-mcp-zero) is for educational & research purposes only.
Automated scraping of LinkedIn may violate their Terms of Service (ToS)
and could lead to account restrictions, IP blocks, or temporary bans.
Always use public guest/browser/voyager/sampling modes responsibly and ethically.
[bold red]================================================================================[/bold red]
"""


def show_disclaimer_if_needed(data_dir: str | Path | None = None) -> None:
    if data_dir is None:
        from platformdirs import user_data_dir

        from linkedin_mcp_zero.config.defaults import DATA_DIR_NAME

        data_dir = user_data_dir(DATA_DIR_NAME)
    data_path = Path(data_dir)
    disclaimer_file = data_path / "disclaimer_accepted.txt"
    if not disclaimer_file.exists():
        Console(stderr=True).print(DISCLAIMER_TEXT)
        try:
            data_path.mkdir(parents=True, exist_ok=True)
            disclaimer_file.write_text("Accepted", encoding="utf-8")
        except Exception:
            pass
