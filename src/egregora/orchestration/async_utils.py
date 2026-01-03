"""Async utilities for orchestration."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any


def run_async_safely(coro: Any) -> Any:
    """Run an async coroutine from a sync context, even if an event loop is already running.

    This is a common problem in environments like Jupyter or when nesting async calls
    in a synchronous framework. Standard `asyncio.run()` will raise a RuntimeError
    if an event loop is already active.

    This function detects a running loop. If found, it runs the coroutine in a
    new thread, avoiding the error. Otherwise, it uses the standard `asyncio.run()`.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop is running, so we can safely start one.
        return asyncio.run(coro)
    else:
        # An event loop is already running.
        # To avoid a RuntimeError, we run the new coroutine in a separate thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
