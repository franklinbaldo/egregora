from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from egregora.llm.rate_limit import (
    AsyncGlobalRateLimiter,
    get_rate_limiter,
    init_rate_limiter,
)


@pytest.mark.asyncio
async def test_global_rate_limiter_acquire_release():
    """Verify basic acquire and release functionality."""
    limiter = AsyncGlobalRateLimiter(requests_per_second=10, max_concurrency=1)
    await limiter.acquire()
    limiter.release()


@pytest.mark.asyncio
async def test_global_rate_limiter_concurrency():
    """Verify that max_concurrency is respected."""
    limiter = AsyncGlobalRateLimiter(requests_per_second=10, max_concurrency=1)

    # Acquire the only available slot
    await limiter.acquire()

    acquired_event = asyncio.Event()

    async def worker():
        await limiter.acquire()
        acquired_event.set()
        limiter.release()

    task = asyncio.create_task(worker())

    # Give the task a chance to run and block
    await asyncio.sleep(0.01)
    assert not acquired_event.is_set()

    limiter.release()  # Release, allowing task to proceed

    # Wait for task
    try:
        await asyncio.wait_for(task, timeout=0.1)
    except TimeoutError:
        pytest.fail("Worker task did not complete in time")

    assert acquired_event.is_set()


@pytest.mark.asyncio
async def test_global_rate_limiter_rate_limiting():
    """Verify that the rate limit is enforced."""
    # 2 requests per second = 0.5s interval
    limiter = AsyncGlobalRateLimiter(requests_per_second=2, max_concurrency=5)

    start = time.monotonic()

    # First call - should be immediate
    await limiter.acquire()
    limiter.release()

    # Second call - should also be immediate (token bucket usually allows burst, or if implementation is strict)
    # Our implementation checks time since last request.
    # If first request set _last_request_time, second request will check diff.
    # Initial _last_request_time is 0.
    # Call 1: time_since_last = now - 0 > 0.5. sleep=0. last=now.
    # Call 2: time_since_last = now - last < 0.5. sleep=0.5 - diff. last=now+sleep.

    await limiter.acquire()
    limiter.release()

    duration = time.monotonic() - start
    # The second acquire should have slept for roughly 0.5s
    assert duration >= 0.45  # allowing some buffer


@pytest.mark.asyncio
async def test_global_rate_limiter_cancellation_safety():
    """Verify that cancelling acquire does not leak semaphore."""
    limiter = AsyncGlobalRateLimiter(requests_per_second=0.1, max_concurrency=1)  # slow rate

    # Make a first request to set the last request time
    await limiter.acquire()
    limiter.release()

    # Try to acquire again - this should sleep because of rate limit
    task = asyncio.create_task(limiter.acquire())

    await asyncio.sleep(0.1)  # Let it enter sleep
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify semaphore is released (value should be 1, so locked() should be False)
    assert not limiter._semaphore.locked(), "Semaphore leaked (remained locked) after cancellation!"


def test_get_rate_limiter_singleton():
    """Verify that get_rate_limiter returns a singleton."""
    limiter1 = get_rate_limiter()
    limiter2 = get_rate_limiter()
    assert limiter1 is limiter2


def test_init_rate_limiter():
    """Verify that init_rate_limiter correctly configures the singleton."""
    # Reset the global limiter for a clean test
    with patch("egregora.llm.rate_limit._limiter", None):
        # First initialization
        init_rate_limiter(requests_per_second=5, max_concurrency=2)
        limiter1 = get_rate_limiter()
        assert limiter1.requests_per_second == 5
        assert limiter1.max_concurrency == 2

        # Subsequent calls to get should return the same instance
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

        # Re-initializing should create a new instance with updated config
        init_rate_limiter(requests_per_second=10, max_concurrency=3)
        limiter3 = get_rate_limiter()
        assert limiter3.requests_per_second == 10
        assert limiter3.max_concurrency == 3
        assert limiter3 is not limiter1

        # Subsequent calls should return the new instance
        limiter4 = get_rate_limiter()
        assert limiter3 is limiter4
