from __future__ import annotations

from typing import Any


async def search_jobs_multi(
    kw: str, loc: str = "", limit: int = 5, age: int = 168
) -> list[dict[str, Any]]:
    try:
        from jobspy import scrape_jobs
    except ImportError:
        return [
            {
                "error": "jobspy_not_installed",
                "hint": "Install with: uv sync --extra multi",
                "kw": kw,
                "loc": loc,
            }
        ]

    jobs = scrape_jobs(
        site_name=["linkedin", "indeed", "google", "zip_recruiter", "glassdoor"],
        search_term=kw,
        location=loc or None,
        results_wanted=limit,
        hours_old=age,
    )
    rows: list[dict[str, Any]] = []
    for _, row in jobs.head(limit * 5).iterrows():
        rows.append(
            {
                "t": str(row.get("title") or ""),
                "co": str(row.get("company") or ""),
                "loc": str(row.get("location") or ""),
                "site": str(row.get("site") or ""),
                "sal": _salary(row),
                "url": str(row.get("job_url") or ""),
            }
        )
    return rows


def _salary(row: Any) -> str:
    min_amount = row.get("min_amount")
    max_amount = row.get("max_amount")
    interval = row.get("interval") or ""
    if min_amount and max_amount:
        return f"{min_amount:g}-{max_amount:g}/{interval}"
    return ""
