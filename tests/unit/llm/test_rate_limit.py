from __future__ import annotations

import threading
import time
from unittest.mock import patch

from egregora.llm.rate_limit import (
    GlobalRateLimiter,
    get_rate_limiter,
    init_rate_limiter,
)


def test_global_rate_limiter_acquire_release():
    """Verify basic acquire and release functionality."""
    limiter = GlobalRateLimiter(requests_per_second=10, max_concurrency=1)
    limiter.acquire()
    limiter.release()


def test_global_rate_limiter_concurrency():
    """Verify that max_concurrency is respected."""
    limiter = GlobalRateLimiter(requests_per_second=10, max_concurrency=1)
    lock_acquired = threading.Event()
    thread_finished = threading.Event()

    def target():
        limiter.acquire()
        lock_acquired.set()
        time.sleep(0.1)
        limiter.release()
        thread_finished.set()

    limiter.acquire()  # Acquire the only available slot in the main thread

    thread = threading.Thread(target=target)
    thread.start()

    # The thread should be blocked trying to acquire the semaphore
    assert not lock_acquired.is_set()

    limiter.release()  # Release the lock, allowing the thread to proceed
    time.sleep(0.01)  # Give the thread time to acquire the lock

    assert lock_acquired.is_set()
    thread.join(timeout=1)
    assert thread_finished.is_set()


@patch("ratelimit.decorators.time.sleep")
def test_global_rate_limiter_rate_limiting(mock_sleep):
    """Verify that the rate limit is enforced."""
    limiter = GlobalRateLimiter(requests_per_second=1, max_concurrency=5)

    # The first call should not sleep
    limiter.acquire()
    limiter.release()
    mock_sleep.assert_not_called()

    # The second call within the same period should sleep
    limiter.acquire()
    limiter.release()
    mock_sleep.assert_called()


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
