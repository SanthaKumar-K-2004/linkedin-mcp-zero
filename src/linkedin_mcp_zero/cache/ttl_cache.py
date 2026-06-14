from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int, max_entries: int = 200) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[Hashable, CacheEntry[T]] = OrderedDict()

    def get(self, key: Hashable) -> T | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return entry.value

    def set(self, key: Hashable, value: T) -> None:
        self._items[key] = CacheEntry(value=value, expires_at=time.monotonic() + self.ttl_seconds)
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)

    def stats(self) -> dict[str, int]:
        return {"entries": len(self._items), "max": self.max_entries, "ttl": self.ttl_seconds}
