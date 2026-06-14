from __future__ import annotations

import asyncio
import time


class TokenBucket:
    def __init__(self, rate_per_second: float, capacity: int) -> None:
        self.rate = rate_per_second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.updated_at
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.updated_at = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await asyncio.sleep((1 - self.tokens) / self.rate)
