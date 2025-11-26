from __future__ import annotations

"""Lightweight tenacity-backed retry helpers."""

from collections.abc import Awaitable, Callable, Iterable
from typing import Any, TypeVar

from pydantic_ai.exceptions import UnexpectedModelBehavior
from tenacity import AsyncRetrying, Retrying, retry_if_exception, stop_after_attempt, wait_random_exponential

RetryableException = UnexpectedModelBehavior

T = TypeVar("T")

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_INITIAL_DELAY = 1.0
_DEFAULT_MAX_DELAY = 10.0
_DEFAULT_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (RetryableException,)
_DEFAULT_RETRY_STATUSES: tuple[str, ...] = ("RESOURCE_EXHAUSTED",)


def _build_retry_predicate(
    retry_on: Iterable[type[BaseException]] = _DEFAULT_RETRY_EXCEPTIONS,
    retry_on_statuses: Iterable[str] = _DEFAULT_RETRY_STATUSES,
):
    status_allow_list = {status.upper() for status in retry_on_statuses}

    def _predicate(exc: BaseException) -> bool:
        status = getattr(exc, "status", None)
        if isinstance(status, str) and status.upper() in status_allow_list:
            return True

        return any(isinstance(exc, exc_type) for exc_type in retry_on)

    return retry_if_exception(_predicate)


def _build_retry_kwargs(
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_delay: float = _DEFAULT_INITIAL_DELAY,
    max_delay: float = _DEFAULT_MAX_DELAY,
    retry_on: Iterable[type[BaseException]] = _DEFAULT_RETRY_EXCEPTIONS,
    retry_on_statuses: Iterable[str] = _DEFAULT_RETRY_STATUSES,
) -> dict[str, Any]:
    return {
        "stop": stop_after_attempt(max_attempts),
        "wait": wait_random_exponential(multiplier=initial_delay, max=max_delay),
        "retry": _build_retry_predicate(retry_on, retry_on_statuses),
        "reraise": True,
    }


def retry_sync[T](
    func: Callable[[], T],
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_delay: float = _DEFAULT_INITIAL_DELAY,
    max_delay: float = _DEFAULT_MAX_DELAY,
    retry_on: Iterable[type[BaseException]] = _DEFAULT_RETRY_EXCEPTIONS,
    retry_on_statuses: Iterable[str] = _DEFAULT_RETRY_STATUSES,
) -> T:
    """Execute ``func`` with retries using tenacity."""
    for attempt in Retrying(
        **_build_retry_kwargs(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            retry_on=retry_on,
            retry_on_statuses=retry_on_statuses,
        )
    ):
        with attempt:
            return func()

    msg = "Retrying yielded no attempts; this should be unreachable"
    raise RuntimeError(msg)


async def retry_async[T](
    func: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_delay: float = _DEFAULT_INITIAL_DELAY,
    max_delay: float = _DEFAULT_MAX_DELAY,
    retry_on: Iterable[type[BaseException]] = _DEFAULT_RETRY_EXCEPTIONS,
    retry_on_statuses: Iterable[str] = _DEFAULT_RETRY_STATUSES,
) -> T:
    """Await ``func`` with retries using tenacity."""
    async for attempt in AsyncRetrying(
        **_build_retry_kwargs(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            retry_on=retry_on,
            retry_on_statuses=retry_on_statuses,
        )
    ):
        with attempt:
            return await func()

    msg = "Async retry yielded no attempts; this should be unreachable"
    raise RuntimeError(msg)
