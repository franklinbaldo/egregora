from __future__ import annotations

import threading
import time
from unittest.mock import patch

from egregora.utils.rate_limit import (
    GlobalRateLimiter,
    get_rate_limiter,
    init_rate_limiter,
)


def test_concurrency_limit():
    """Verify that only `max_concurrency` threads can acquire the limiter at once."""
    limiter = GlobalRateLimiter(requests_per_second=100, max_concurrency=2)
    lock1 = threading.Lock()
    lock2 = threading.Lock()

    lock1.acquire()
    lock2.acquire()

    acquired_count = 0
    lock = threading.Lock()

    def worker():
        nonlocal acquired_count
        limiter.acquire()
        with lock:
            acquired_count += 1
        time.sleep(0.1)
        limiter.release()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()

    time.sleep(0.05)
    with lock:
        assert acquired_count == 2

    for t in threads:
        t.join()

    assert acquired_count == 5


def test_rate_limit_slow():
    """Verify that calling `acquire` slower than the rate limit does not block."""
    limiter = GlobalRateLimiter(requests_per_second=10, max_concurrency=1)
    start_time = time.time()
    for _ in range(5):
        limiter.acquire()
        limiter.release()
        time.sleep(0.11)
    end_time = time.time()
    # Should take roughly 5 * 0.11s = 0.55s
    assert end_time - start_time >= 0.55


def test_rate_limit_fast():
    """Verify that calling `acquire` faster than the rate limit blocks."""
    # With 2 requests per second, 2 calls are allowed per 1-second window.
    rps = 2
    limiter = GlobalRateLimiter(requests_per_second=rps, max_concurrency=1)

    start_time = time.time()
    # Make 3 calls. The first 2 should be fast. The 3rd call should block
    # until the 1-second window resets.
    for _ in range(3):
        limiter.acquire()
        limiter.release()
    end_time = time.time()

    duration = end_time - start_time
    # The total time should be a bit over 1s for the 3rd call to wait.
    assert 0.95 < duration < 1.05


def test_global_singleton_management():
    """Verify that get_rate_limiter and init_rate_limiter manage a singleton."""
    # Reset global state for clean test
    with patch("egregora.utils.rate_limit._limiter", None):
        # 1. Get default limiter
        limiter1 = get_rate_limiter()
        assert limiter1.requests_per_second == 1.0
        assert limiter1.max_concurrency == 1

        # 2. Get it again, should be the same instance
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

        # 3. Initialize with new values
        init_rate_limiter(requests_per_second=5.0, max_concurrency=3)
        limiter3 = get_rate_limiter()
        assert limiter3.requests_per_second == 5.0
        assert limiter3.max_concurrency == 3
        assert limiter3 is not limiter1

        # 4. Get it again, should be the new initialized instance
        limiter4 = get_rate_limiter()
        assert limiter3 is limiter4


def test_context_manager():
    """Verify the context manager correctly acquires and releases the semaphore."""
    limiter = GlobalRateLimiter(requests_per_second=100, max_concurrency=1)

    # Check initial state of the semaphore's internal counter
    assert limiter._semaphore._value == 1

    with limiter:
        # Check that the semaphore was acquired
        assert limiter._semaphore._value == 0

    # Check that the semaphore was released
    assert limiter._semaphore._value == 1
