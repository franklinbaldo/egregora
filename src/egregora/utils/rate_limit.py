from __future__ import annotations

import asyncio
import time
from collections import deque


class AsyncRateLimit:
    """Simple async rate limiter (max calls per period in seconds)."""

    def __init__(self, max_calls: int, period: float = 1.0) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        if period <= 0:
            raise ValueError("period must be > 0")
        self._max_calls = max_calls
        self._period = period
        self._usage = deque[float]()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Await until the next call is allowed."""
        async with self._lock:
            now = time.monotonic()
            self._purge(now)
            if len(self._usage) >= self._max_calls:
                wait_time = self._period - (now - self._usage[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                now = time.monotonic()
                self._purge(now)
            self._usage.append(now)

    def _purge(self, now: float) -> None:
        period = self._period
        while self._usage and now - self._usage[0] >= period:
            self._usage.popleft()
