from __future__ import annotations

import asyncio
import inspect
import threading
import time
from collections import deque
from collections.abc import Awaitable
from typing import Protocol


class _RateLimitState:
    def __init__(self, max_calls: int, period: float) -> None:
        if max_calls < 1:
            msg = "max_calls must be >= 1"
            raise ValueError(msg)
        if period <= 0:
            msg = "period must be > 0"
            raise ValueError(msg)
        self._max_calls = max_calls
        self._period = period
        self._usage = deque[float]()

    def reserve(self, now: float) -> float:
        self._purge(now)
        if len(self._usage) >= self._max_calls:
            return max(0.0, self._period - (now - self._usage[0]))
        self._usage.append(now)
        return 0.0

    def record(self, now: float) -> None:
        self._purge(now)
        self._usage.append(now)

    def _purge(self, now: float) -> None:
        period = self._period
        while self._usage and now - self._usage[0] >= period:
            self._usage.popleft()


class RateLimiter(Protocol):
    def acquire(self) -> Awaitable[None] | None:  # pragma: no cover - protocol
        """Reserve a rate limit slot, blocking or awaiting as needed."""


class AsyncRateLimiter:
    """Async rate limiter (max calls per period in seconds)."""

    def __init__(self, max_calls: int, period: float = 1.0) -> None:
        self._state = _RateLimitState(max_calls, period)
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Await until the next call is allowed."""
        async with self._lock:
            await self._wait()

    async def _wait(self) -> None:
        now = time.monotonic()
        wait_time = self._state.reserve(now)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
            self._state.record(time.monotonic())


class SyncRateLimiter:
    """Synchronous rate limiter (max calls per period in seconds)."""

    def __init__(self, max_calls: int, period: float = 1.0) -> None:
        self._state = _RateLimitState(max_calls, period)
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until the next call is allowed."""
        with self._lock:
            now = time.monotonic()
            wait_time = self._state.reserve(now)
            if wait_time > 0:
                time.sleep(wait_time)
                self._state.record(time.monotonic())


async def apply_rate_limit(rate_limit: RateLimiter | None) -> None:
    """Apply a rate limiter regardless of sync/async implementation."""
    if rate_limit is None:
        return

    result = rate_limit.acquire()
    if inspect.isawaitable(result):
        await result
