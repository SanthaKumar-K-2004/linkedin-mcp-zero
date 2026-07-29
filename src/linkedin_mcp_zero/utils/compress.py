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


# Word-boundary-safe, longest-first: plain str.replace on these keys mangles
# locations (e.g. "Indiana" contained "India" -> "INna", and "New Yorker"
# became "NYer"). Note: "Canada" is deliberately NOT mapped — "CA" is already
# the standard abbreviation for California, and an explicit "Canada" in the
# output is worth 3 extra tokens to avoid that ambiguity.
_LOCATION_ALIASES: dict[str, str] = {
    "United States": "US",
    "United Kingdom": "UK",
    "New York": "NY",
    "California": "CA",
    "Netherlands": "NL",
    "Singapore": "SG",
    "Australia": "AU",
    "Germany": "DE",
    "France": "FR",
    "Spain": "ES",
    "Italy": "IT",
    "Sweden": "SE",
    "Brazil": "BR",
    "Japan": "JP",
    "India": "IN",
}


def _boundary_pattern(phrase: str) -> re.Pattern[str]:
    words = r"\s+".join(re.escape(word) for word in phrase.split())
    return re.compile(rf"\b{words}\b")


_LOCATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_boundary_pattern(phrase), alias)
    for phrase, alias in sorted(_LOCATION_ALIASES.items(), key=lambda kv: -len(kv[0]))
]


def compact_location(location: str | None) -> str:
    text = clean_text(location)
    for pattern, alias in _LOCATION_PATTERNS:
        text = pattern.sub(alias, text)
    return text


def relative_age(date_text: str | None, now: datetime | None = None) -> str:
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
    current = now or datetime.now(timezone.utc)
    delta = current.astimezone(timezone.utc) - posted.astimezone(timezone.utc)
    if delta.total_seconds() < 0:
        # Future-dated posting (clock skew or stale markup): report "now"
        # instead of a nonsense negative/near-24h value.
        return "0h"
    if delta.days >= 30:
        return f"{delta.days // 30}mo"
    if delta.days >= 7:
        return f"{delta.days // 7}w"
    if delta.days >= 1:
        return f"{delta.days}d"
    return f"{max(1, delta.seconds // 3600)}h"
