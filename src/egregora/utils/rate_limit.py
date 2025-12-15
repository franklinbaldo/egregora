"""Global rate limiter for LLM API calls."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GlobalRateLimiter:
    """Thread-safe global rate limiter using token bucket and semaphore.
    
    Supports refunding tokens on failed requests (e.g., 429 errors) to allow
    immediate retry with fallback models without waiting for rate limit reset.
    """

    requests_per_second: float = 1.0
    max_concurrency: int = 1

    _tokens: float = 1.0
    _last_update: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _semaphore: threading.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self._semaphore = threading.Semaphore(self.max_concurrency)
        self._tokens = self.requests_per_second

    def acquire(self) -> None:
        """Acquire permission to make a request. Blocks if limits are reached."""
        # 1. Concurrency limit (Semaphore)
        self._semaphore.acquire()

        try:
            # 2. Rate limit (Token Bucket)
            with self._lock:
                now = time.time()
                elapsed = now - self._last_update
                self._last_update = now

                # Refill tokens - use max(1.0, ...) as bucket cap to support
                # refund() which adds 1.0 token for immediate fallback
                bucket_cap = max(1.0, self.requests_per_second)
                self._tokens = min(
                    bucket_cap, self._tokens + elapsed * self.requests_per_second
                )

                if self._tokens < 1.0:
                    # Need to wait
                    wait_time = (1.0 - self._tokens) / self.requests_per_second
                    logger.debug("Rate limit hit, waiting %.2fs", wait_time)
                    time.sleep(wait_time)
                    self._tokens = 0.0
                else:
                    self._tokens -= 1.0
        except Exception:
            # If rate limit logic fails, release semaphore
            self._semaphore.release()
            raise

    def release(self) -> None:
        """Release concurrency slot."""
        self._semaphore.release()

    def refund(self) -> None:
        """Refund a token to the bucket after a failed request (e.g., 429 error).
        
        This allows immediate retry with fallback models without waiting for
        the rate limit to reset. Call this when a request fails with a rate
        limit error to allow the next model in a FallbackModel chain to try
        immediately.
        """
        with self._lock:
            # Add back the token that was consumed
            # Use max(1.0, ...) to ensure we can always make at least one request
            # even if requests_per_second is very low (e.g., 0.05)
            bucket_cap = max(1.0, self.requests_per_second)
            self._tokens = min(bucket_cap, self._tokens + 1.0)
            logger.info("Rate limit token refunded, tokens=%.2f (cap=%.2f)", self._tokens, bucket_cap)


# Global singleton instance
_limiter: GlobalRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> GlobalRateLimiter:
    """Get or create the global rate limiter singleton."""
    global _limiter  # noqa: PLW0603
    with _limiter_lock:
        if _limiter is None:
            # Default to conservative limits if not initialized
            _limiter = GlobalRateLimiter(requests_per_second=1.0, max_concurrency=1)
    return _limiter


def init_rate_limiter(requests_per_second: float, max_concurrency: int) -> None:
    """Initialize the global rate limiter with specific config."""
    global _limiter  # noqa: PLW0603
    with _limiter_lock:
        _limiter = GlobalRateLimiter(requests_per_second=requests_per_second, max_concurrency=max_concurrency)
    logger.info(
        "Initialized global rate limiter: %s req/s, %s concurrent", requests_per_second, max_concurrency
    )
