"""Async utilities."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any


def run_async_safely(coro: Any) -> Any:
    """Run an async coroutine from a synchronous context, safely handling nested event loops.

    If an event loop is already running (e.g., in Jupyter or nested calls),
    this function will run the coroutine in a new thread to avoid a `RuntimeError`.
    Otherwise, it uses `asyncio.run()`.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - use asyncio.run()
        return asyncio.run(coro)
    else:
        # Loop is already running - run asyncio.run in a new thread.
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
