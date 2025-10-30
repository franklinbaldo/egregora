from __future__ import annotations

from typing import Any, Callable, TypeVar

T = TypeVar("T")

def call_with_retries_sync(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T: ...

def call_with_retries(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any: ...

def sleep_with_progress_sync(delay: float, description: str) -> None: ...
