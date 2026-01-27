"""Global rate limiter for LLM API calls."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
<<<<<<< HEAD
from collections.abc import AsyncIterator
=======
>>>>>>> origin/pr/2704
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class AsyncGlobalRateLimiter:
    """An asyncio-native rate limiter that enforces max concurrency and requests per second."""

    def __init__(self, requests_per_second: float, max_concurrency: int) -> None:
        self.requests_per_second = requests_per_second
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()  # To protect _last_request_time updates

    async def acquire(self) -> None:
        """Acquire permission to make a request. Suspends if limits are reached."""
        # 1. Enforce Concurrency Limit
        await self._semaphore.acquire()

        try:
            # 2. Enforce Rate Limit (Requests per Second)
            interval = 1.0 / self.requests_per_second

            async with self._lock:
                now = time.monotonic()
                time_since_last = now - self._last_request_time

                if time_since_last < interval:
                    sleep_time = interval - time_since_last
                    self._last_request_time = now + sleep_time
                else:
                    sleep_time = 0
                    self._last_request_time = now

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        except BaseException:
            # Release semaphore if we are cancelled or fail during sleep
            self._semaphore.release()
            raise

    def release(self) -> None:
        """Release concurrency slot."""
        self._semaphore.release()

    @asynccontextmanager
<<<<<<< HEAD
    async def throttle(self) -> AsyncIterator[None]:
=======
    async def throttle(self):
>>>>>>> origin/pr/2704
        """Context manager for rate limiting."""
        await self.acquire()
        try:
            yield
        finally:
            self.release()


# Global singleton instance
_limiter: AsyncGlobalRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> AsyncGlobalRateLimiter:
    """Get or create the global rate limiter singleton."""
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                # Default to conservative limits if not initialized
                _limiter = AsyncGlobalRateLimiter(requests_per_second=1.0, max_concurrency=1)
    return _limiter


def init_rate_limiter(requests_per_second: float, max_concurrency: int) -> None:
    """Initialize the global rate limiter with specific config."""
    global _limiter
    with _limiter_lock:
<<<<<<< HEAD
        _limiter = AsyncGlobalRateLimiter(
            requests_per_second=requests_per_second, max_concurrency=max_concurrency
        )
=======
        _limiter = AsyncGlobalRateLimiter(requests_per_second=requests_per_second, max_concurrency=max_concurrency)
>>>>>>> origin/pr/2704
    logger.info(
        "Initialized global async rate limiter: %s req/s, %s concurrent",
        requests_per_second,
        max_concurrency,
    )
