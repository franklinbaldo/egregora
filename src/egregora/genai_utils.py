"""Shared helpers for working with the google.genai SDK."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from google.api_core import exceptions as google_api_exceptions
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TimeRemainingColumn

logger = logging.getLogger(__name__)
_console = Console(stderr=True, soft_wrap=True)

_RateLimitFn = TypeVar("_RateLimitFn", bound=Callable[..., Awaitable[Any]])

# Ensure we space out requests so we do not burst through short-term quota limits.
_rate_lock = asyncio.Lock()
_last_call_monotonic = 0.0
_sync_rate_lock = threading.Lock()
_sync_last_call_monotonic = 0.0
_MIN_INTERVAL_SECONDS = 1.5  # free tier tolerates ~40 RPM, so keep a healthy gap


_RETRYABLE_EXCEPTIONS = (
    google_api_exceptions.ResourceExhausted,
    google_api_exceptions.ServiceUnavailable,
    google_api_exceptions.InternalServerError,
    google_api_exceptions.DeadlineExceeded,
)


def _is_rate_limit_error(error: Exception) -> bool:
    """Return True when ``error`` looks like a quota/rate limit or transient failure."""
    message = str(error).lower()
    return any(
        token in message
        for token in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "503",
            "unavailable",
            "overloaded",
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


def is_rate_limit_error(error: Exception) -> bool:
    """Public helper to determine if an error is retryable."""
    return _is_rate_limit_error(error)


def extract_retry_delay(error: Exception) -> float | None:
    """Expose retry delay parsing for synchronous helpers."""
    return _extract_retry_delay(error)


async def _respect_min_interval() -> None:
    """Wait if necessary so consecutive API calls honour `_MIN_INTERVAL_SECONDS`."""
    global _last_call_monotonic  # noqa: PLW0603
    async with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_call_monotonic
        if elapsed < _MIN_INTERVAL_SECONDS:
            await asyncio.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            now = time.monotonic()
        _last_call_monotonic = now


def _respect_min_interval_sync() -> None:
    """Synchronous equivalent of `_respect_min_interval`."""
    global _sync_last_call_monotonic  # noqa: PLW0603
    with _sync_rate_lock:
        now = time.monotonic()
        elapsed = now - _sync_last_call_monotonic
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            now = time.monotonic()
        _sync_last_call_monotonic = now


async def _sleep_with_progress(delay: float, description: str) -> None:
    """Sleep for ``delay`` seconds, showing a progress bar when interactive."""

    if delay <= 0:
        return

    if not _console.is_terminal or os.environ.get("EGREGORA_PROGRESS", "0").lower() not in {
        "1",
        "true",
        "yes",
    }:
        await asyncio.sleep(delay)
        return

    progress = Progress(
        SpinnerColumn(),
        BarColumn(bar_width=None),
        TimeRemainingColumn(),
        console=_console,
        transient=True,
    )

    start_time = time.monotonic()
    with progress:
        task_id = progress.add_task(description, total=delay)

        while True:
            elapsed = time.monotonic() - start_time
            progress.update(task_id, completed=min(elapsed, delay))
            if elapsed >= delay:
                break
            await asyncio.sleep(min(0.5, delay - elapsed))


def _sleep_with_progress_sync(delay: float, description: str) -> None:
    """Synchronous sleep that mirrors `_sleep_with_progress`."""
    if delay <= 0:
        return

    if not _console.is_terminal or os.environ.get("EGREGORA_PROGRESS", "0").lower() not in {
        "1",
        "true",
        "yes",
    }:
        time.sleep(delay)
        return

    progress = Progress(
        SpinnerColumn(),
        BarColumn(bar_width=None),
        TimeRemainingColumn(),
        console=_console,
        transient=True,
    )

    start_time = time.monotonic()
    with progress:
        task_id = progress.add_task(description, total=delay)

        while True:
            elapsed = time.monotonic() - start_time
            progress.update(task_id, completed=min(elapsed, delay))
            if elapsed >= delay:
                break
            time.sleep(min(0.5, delay - elapsed))


async def call_with_retries[**P, T](
    async_fn: Callable[P, Awaitable[T]],
    *args: P.args,
    max_attempts: int = 5,
    base_delay: float = 2.0,
    **kwargs: P.kwargs,
) -> T:
    """Invoke ``async_fn`` retrying on rate-limit errors with adaptive delays."""
    attempt = 1
    fn_name = getattr(async_fn, "__qualname__", repr(async_fn))

    while True:
        await _respect_min_interval()
        try:
            return await async_fn(*args, **kwargs)
        except _RETRYABLE_EXCEPTIONS as exc:
            handled_exc: Exception = exc
        except Exception as exc:  # noqa: BLE001
            if not _is_rate_limit_error(exc) or attempt >= max_attempts:
                raise
            handled_exc = exc

        recommended_delay = _extract_retry_delay(handled_exc)
        if recommended_delay is not None:
            delay = max(recommended_delay, 0.0)
        else:
            delay = base_delay * (2 ** (attempt - 1))

        logger.info(
            f"[yellow]⏳ Retry[/] {fn_name} — attempt {attempt}/{max_attempts}. "
            f"Waiting {delay:.2f}s before retry.\n[dim]{handled_exc}[/]"
        )

        await _sleep_with_progress(delay, f"Rate limit cooldown ({delay:.0f}s)")
        attempt += 1


def call_with_retries_sync(
    fn: Callable[..., Any],
    *args: Any,
    max_attempts: int = 5,
    base_delay: float = 2.0,
    **kwargs: Any,
) -> Any:
    """Synchronous twin of ``call_with_retries`` for Batch API usage."""
    attempt = 1
    fn_name = getattr(fn, "__qualname__", repr(fn))

    while True:
        _respect_min_interval_sync()
        try:
            return fn(*args, **kwargs)
        except _RETRYABLE_EXCEPTIONS as exc:
            handled_exc: Exception = exc
        except Exception as exc:  # noqa: BLE001
            if not _is_rate_limit_error(exc) or attempt >= max_attempts:
                raise
            handled_exc = exc

        recommended_delay = _extract_retry_delay(handled_exc)
        if recommended_delay is not None:
            delay = max(recommended_delay, 0.0)
        else:
            delay = base_delay * (2 ** (attempt - 1))

        logger.info(
            f"[yellow]⏳ Retry[/] {fn_name} — attempt {attempt}/{max_attempts}. "
            f"Waiting {delay:.2f}s before retry.\n[dim]{handled_exc}[/]"
        )

        _sleep_with_progress_sync(delay, f"Rate limit cooldown ({delay:.0f}s)")
        attempt += 1


def sleep_with_progress_sync(delay: float, description: str) -> None:
    """Public wrapper around the synchronous sleep helper."""
    _sleep_with_progress_sync(delay, description)
