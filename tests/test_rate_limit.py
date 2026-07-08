import time

import pytest

from linkedin_mcp_zero.utils.rate_limit import TokenBucket


@pytest.mark.asyncio
async def test_token_bucket_acquire_immediate() -> None:
    bucket = TokenBucket(rate_per_second=100.0, capacity=2)
    # Both tokens are available initially, so we can acquire twice without waiting
    await bucket.acquire()
    await bucket.acquire()
    assert bucket.tokens < 0.1  # Virtually 0 tokens left


@pytest.mark.asyncio
async def test_token_bucket_rate_replenish() -> None:
    bucket = TokenBucket(rate_per_second=100.0, capacity=2)
    await bucket.acquire()
    await bucket.acquire()
    # Mocking elapsed time by shifting updated_at
    bucket.updated_at -= 0.02  # 0.02s elapsed, should add 2.0 tokens (0.02 * 100 = 2.0)
    await bucket.acquire()  # Should succeed immediately


@pytest.mark.asyncio
async def test_token_bucket_wait() -> None:
    bucket = TokenBucket(rate_per_second=100.0, capacity=1)
    await bucket.acquire()  # Consume the only token

    start_time = time.monotonic()
    await bucket.acquire()  # Must wait for ~0.01s
    elapsed = time.monotonic() - start_time
    assert elapsed >= 0.009  # Allow slight timing tolerance
