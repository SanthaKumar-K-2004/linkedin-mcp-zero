import time
from unittest.mock import patch
from linkedin_mcp_zero.cache.ttl_cache import TTLCache

def test_cache_get_set() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=10)
    cache.set("key1", "val1")
    assert cache.get("key1") == "val1"
    assert cache.get("key2") is None

def test_cache_expiration() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=1, max_entries=10)
    with patch("time.monotonic", return_value=100.0):
        cache.set("key1", "val1")
        assert cache.get("key1") == "val1"

    # Advance monotonic clock past TTL
    with patch("time.monotonic", return_value=102.0):
        assert cache.get("key1") is None

def test_cache_eviction_lru() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=2)
    cache.set("key1", "val1")
    cache.set("key2", "val2")
    cache.set("key3", "val3")

    assert cache.get("key1") is None  # Evicted
    assert cache.get("key2") == "val2"
    assert cache.get("key3") == "val3"

def test_cache_stats() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=10, max_entries=100)
    cache.set("a", "1")
    cache.set("b", "2")
    stats = cache.stats()
    assert stats["entries"] == 2
    assert stats["max"] == 100
    assert stats["ttl"] == 10
