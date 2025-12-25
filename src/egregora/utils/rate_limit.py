"""Global rate limiter for LLM API calls."""

from __future__ import annotations

import logging
import threading
from types import TracebackType

from ratelimit import limits, sleep_and_retry

logger = logging.getLogger(__name__)


class GlobalRateLimiter:
    """A wrapper for the `ratelimit` library that also enforces max concurrency."""

    def __init__(self, requests_per_second: float, max_concurrency: int) -> None:
        self.requests_per_second = requests_per_second
        self.max_concurrency = max_concurrency
        self._semaphore = threading.Semaphore(self.max_concurrency)

        # Create a dummy decorated function to reuse the ratelimit logic
        @sleep_and_retry
        @limits(calls=int(self.requests_per_second), period=1)
        def _dummy_call() -> None:
            pass

        self._rate_limited_call = _dummy_call

    def __enter__(self) -> None:
        self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()

    def acquire(self) -> None:
        """Acquire permission to make a request. Blocks if limits are reached."""
        self._semaphore.acquire()
        try:
            self._rate_limited_call()
        except Exception:
            self._semaphore.release()
            raise

    def release(self) -> None:
        """Release concurrency slot."""
        self._semaphore.release()


# Global singleton instance
_limiter: GlobalRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> GlobalRateLimiter:
    """Get or create the global rate limiter singleton."""
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                # Default to conservative limits if not initialized
                _limiter = GlobalRateLimiter(requests_per_second=1.0, max_concurrency=1)
    return _limiter


def init_rate_limiter(requests_per_second: float, max_concurrency: int) -> None:
    """Initialize the global rate limiter with specific config."""
    global _limiter
    with _limiter_lock:
        _limiter = GlobalRateLimiter(requests_per_second=requests_per_second, max_concurrency=max_concurrency)
    logger.info(
        "Initialized global rate limiter: %s req/s, %s concurrent",
        requests_per_second,
        max_concurrency,
    )
