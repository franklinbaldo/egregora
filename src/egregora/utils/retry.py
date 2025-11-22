from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from pydantic_ai.exceptions import UnexpectedModelBehavior

RetryableException = UnexpectedModelBehavior


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 10.0
    multiplier: float = 1.5
    jitter: float = 0.3
    retry_on: Iterable[type[BaseException]] = (RetryableException,)

    def should_retry(self, attempt: int, exc: BaseException) -> bool:
        if attempt >= self.max_attempts - 1:
            return False
        return any(isinstance(exc, exc_type) for exc_type in self.retry_on)

    def next_delay(self, attempt: int) -> float:
        delay = min(self.max_delay, self.initial_delay * (self.multiplier**attempt))
        jitter = random.uniform(-self.jitter, self.jitter)  # noqa: S311
        return max(0.0, delay + jitter)


async def retry_async(func: Callable[[], asyncio.Future], policy: RetryPolicy) -> any:
    last_error: BaseException | None = None
    for attempt in range(policy.max_attempts):
        try:
            return await func()
        except BaseException as exc:
            last_error = exc
            if not policy.should_retry(attempt, exc):
                raise
            await asyncio.sleep(policy.next_delay(attempt))
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
            time_to_wait = policy.next_delay(attempt)
            time.sleep(time_to_wait)
    if last_error:
        raise last_error
    return None
