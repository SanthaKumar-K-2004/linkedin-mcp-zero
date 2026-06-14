from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape

WS_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return WS_RE.sub(" ", unescape(value)).strip()


def truncate(value: str | None, max_chars: int = 220) -> str:
    text = clean_text(value)
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:-")
    return f"{cut}..."


def compact_dict(data: dict[str, object | None | list[object]]) -> dict[str, object]:
    return {k: v for k, v in data.items() if v not in (None, "", [], {})}


def compact_location(location: str | None) -> str:
    text = clean_text(location)
    replacements = {
        "United States": "US",
        "United Kingdom": "UK",
        "California": "CA",
        "New York": "NY",
        "India": "IN",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def relative_age(date_text: str | None) -> str:
    text = clean_text(date_text)
    if not text:
        return ""
    if any(unit in text.lower() for unit in ("hour", "day", "week", "month", "year")):
        return (
            text.lower()
            .replace("hours", "h")
            .replace("hour", "h")
            .replace("days", "d")
            .replace("day", "d")
            .replace("weeks", "w")
            .replace("week", "w")
            .replace("months", "mo")
            .replace("month", "mo")
            .replace("years", "y")
            .replace("year", "y")
            .replace(" ago", "")
        )
    try:
        posted = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    delta = datetime.now(timezone.utc) - posted.astimezone(timezone.utc)
    if delta.days >= 30:
        return f"{delta.days // 30}mo"
    if delta.days >= 7:
        return f"{delta.days // 7}w"
    if delta.days >= 1:
        return f"{delta.days}d"
    return f"{max(1, delta.seconds // 3600)}h"
