from __future__ import annotations

import json
from collections.abc import Iterable

from selectolax.parser import HTMLParser


def extract_json_ld(html: str) -> list[dict[str, object]]:
    parser = HTMLParser(html)
    values: list[dict[str, object]] = []
    for tag in parser.css('script[type="application/ld+json"]'):
        raw = tag.text()
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            values.append(parsed)
        elif isinstance(parsed, list):
            values.extend(item for item in parsed if isinstance(item, dict))
    return values


def first_job_posting(items: Iterable[dict[str, object]]) -> dict[str, object] | None:
    for item in items:
        types = item.get("@type")
        if types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types):
            return item
    return None
