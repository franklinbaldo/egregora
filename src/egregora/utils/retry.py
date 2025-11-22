from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from pydantic_ai.exceptions import UnexpectedModelBehavior

RetryableException = UnexpectedModelBehavior


def _parse_retry_delay(value: str | float | None) -> float | None:
    if value is None:
        return None

    if isinstance(value, int | float):
        return float(value)

    if isinstance(value, str):
        duration = 0.0
        for match in re.finditer(r"(?P<value>\d+(?:\.\d+)?)(?P<unit>[hmsHMS])?", value):
            number = float(match.group("value"))
            unit = match.group("unit") or "s"
            unit = unit.lower()
            if unit == "h":
                duration += number * 3600
            elif unit == "m":
                duration += number * 60
            else:
                duration += number
        return duration or None

    return None


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 10.0
    multiplier: float = 1.5
    jitter: float = 0.3
    retry_on: Iterable[type[BaseException]] = (RetryableException,)
    retry_on_statuses: Iterable[str] = ("RESOURCE_EXHAUSTED",)

    def should_retry(self, attempt: int, exc: BaseException) -> bool:
        status = getattr(exc, "status", None)
        if isinstance(status, str):
            status_upper = status.upper()
            for allowed in self.retry_on_statuses:
                if status_upper == allowed.upper():
                    return attempt < self.max_attempts - 1

        if attempt >= self.max_attempts - 1:
            return False

        return any(isinstance(exc, exc_type) for exc_type in self.retry_on)

    def next_delay(self, attempt: int, exc: BaseException | None = None) -> float:
        delay_from_exc = self._retry_delay_from_exception(exc)
        if delay_from_exc is not None:
            return min(self.max_delay, delay_from_exc)

        delay = min(self.max_delay, self.initial_delay * (self.multiplier**attempt))
        jitter = random.uniform(-self.jitter, self.jitter)  # noqa: S311
        return max(0.0, delay + jitter)

    def _retry_delay_from_exception(self, exc: BaseException | None) -> float | None:
        if exc is None:
            return None

        details = getattr(exc, "details", None)
        retry_delay = None

        if isinstance(details, dict):
            retry_delay = details.get("retryDelay")
        elif isinstance(details, list):
            for entry in details:
                if isinstance(entry, dict):
                    retry_delay = entry.get("retryDelay")
                    if retry_delay is not None:
                        break

        return _parse_retry_delay(retry_delay)


async def retry_async(func: Callable[[], asyncio.Future], policy: RetryPolicy) -> any:
    last_error: BaseException | None = None
    for attempt in range(policy.max_attempts):
        try:
            return await func()
        except BaseException as exc:
            last_error = exc
            if not policy.should_retry(attempt, exc):
                raise
            await asyncio.sleep(policy.next_delay(attempt, exc))
    if last_error:
        raise last_error
    return None


def retry_sync(func: Callable[[], any], policy: RetryPolicy) -> any:
    last_error: BaseException | None = None
    for attempt in range(policy.max_attempts):
        try:
            return func()
        except BaseException as exc:
            last_error = exc
            if not policy.should_retry(attempt, exc):
                raise
            time_to_wait = policy.next_delay(attempt, exc)
            time.sleep(time_to_wait)
    if last_error:
        raise last_error
    return None
