from __future__ import annotations

import re

_NUM_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?|\.\d+")
_HOURLY_TO_YEARLY = 2080  # 40 h/week * 52 weeks


def parse_min_salary(text: str | None) -> int | None:
    """Extract the minimum annualized salary number from free-form text.

    Handles compact ("$150K-180K/yr"), comma-grouped ("$120,000 - $150,000"),
    decimal hourly ("$45.00/hr"), and mixed ("95k a year") representations.
    Returns None when nothing parseable is present.
    """
    if not text:
        return None
    lowered = text.lower()
    matches = _NUM_RE.findall(text.replace("\u00a0", " "))
    values: list[float] = []
    for raw in matches:
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        # A bare small number followed by a "k" anywhere in the string is
        # almost certainly thousands ("150K", "95k a year").
        if value < 1000 and "k" in lowered:
            value *= 1000
        values.append(value)
    if not values:
        return None
    minimum = min(values)
    # Normalize hourly/daily-ish figures to an annual equivalent so they can
    # be compared against yearly minimums.
    hourly = "hr" in lowered or "hour" in lowered
    if hourly and minimum < 1000:  # genuine hourly rate like 45 or 45.50
        minimum *= _HOURLY_TO_YEARLY
    return int(minimum)


def salary_meets_minimum(text: str | None, min_salary: int) -> bool:
    """True when text has no salary info (keep the job) or meets the minimum."""
    if min_salary <= 0:
        return True
    value = parse_min_salary(text)
    if value is None:
        return True
    return value >= min_salary
