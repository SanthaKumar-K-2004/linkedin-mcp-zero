from __future__ import annotations

import json
from collections.abc import Iterable

from bs4 import BeautifulSoup


def extract_json_ld(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "lxml")
    values: list[dict[str, object]] = []
    for tag in soup.select('script[type="application/ld+json"]'):
        raw = tag.string or tag.get_text()
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
