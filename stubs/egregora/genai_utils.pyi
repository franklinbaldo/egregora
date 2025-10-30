from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

_T = TypeVar("_T")


def call_with_retries(
    async_fn: Callable[..., Awaitable[_T]],
    *args: object,
    **kwargs: object,
) -> Awaitable[_T]: ...


def call_with_retries_sync(
    fn: Callable[..., _T],
    *args: object,
    **kwargs: object,
) -> _T: ...


def sleep_with_progress_sync(delay: float, description: str) -> None: ...
