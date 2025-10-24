"""Shared helpers for working with the google.genai SDK."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar


logger = logging.getLogger(__name__)

_RateLimitFn = TypeVar("_RateLimitFn", bound=Callable[..., Awaitable[Any]])

# Ensure we space out requests so we do not burst through short-term quota limits.
_rate_lock = asyncio.Lock()
_last_call_monotonic = 0.0
_MIN_INTERVAL_SECONDS = 1.5  # free tier tolerates ~40 RPM, so keep a healthy gap


def _is_rate_limit_error(error: Exception) -> bool:
    """Return True when ``error`` looks like a quota/rate limit failure."""
    message = str(error).lower()
    return any(
        token in message
        for token in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
        )
    )


def _extract_retry_delay(error: Exception) -> float | None:
    """Try to extract server-recommended retry delay from the error message."""
    text = str(error)

    # gRPC style: `'retryDelay': '19s'`
    match = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+)(?:\.(\d+))?s['\"]", text)
    if match:
        seconds = int(match.group(1))
        fractional = match.group(2)
        if fractional:
            seconds += float(f"0.{fractional}")
        return float(seconds)

    # REST style: `Retry-After: 20`
    match = re.search(r"retry-after[:=]\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return float(match.group(1))

    return None


async def _respect_min_interval() -> None:
    """Wait if necessary so consecutive API calls honour `_MIN_INTERVAL_SECONDS`."""
    global _last_call_monotonic
    async with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_call_monotonic
        if elapsed < _MIN_INTERVAL_SECONDS:
            await asyncio.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            now = time.monotonic()
        _last_call_monotonic = now


async def call_with_retries(
    async_fn: _RateLimitFn,
    *args: Any,
    max_attempts: int = 8,
    base_delay: float = 2.0,
    **kwargs: Any,
) -> Any:
    """Invoke ``async_fn`` retrying on rate-limit errors with adaptive delays."""
    attempt = 1
    fn_name = getattr(async_fn, "__qualname__", repr(async_fn))

    while True:
        await _respect_min_interval()
        try:
            return await async_fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if not _is_rate_limit_error(exc) or attempt >= max_attempts:
                raise

            recommended_delay = _extract_retry_delay(exc)
            if recommended_delay is not None:
                delay = recommended_delay + 1.0  # pad slightly beyond the server hint
            else:
                delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Rate limit for %s (attempt %s/%s). Retrying in %.2fs%s",
                fn_name,
                attempt,
                max_attempts,
                delay,
                f". Server suggested %.2fs. Details: %s" % (recommended_delay, exc)
                if recommended_delay is not None
                else f": {exc}",
            )

            await asyncio.sleep(delay)
            attempt += 1
