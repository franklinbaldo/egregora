"""Tests for async utilities."""

from __future__ import annotations

import asyncio

import pytest

from egregora.orchestration.async_utils import run_async_safely


async def sample_coroutine() -> str:
    """A simple coroutine for testing."""
    await asyncio.sleep(0.01)
    return "done"


def test_run_async_safely_without_running_loop():
    """Verify it runs a coroutine when no loop is active."""
    result = run_async_safely(sample_coroutine())
    assert result == "done"


@pytest.mark.asyncio
async def test_run_async_safely_with_running_loop():
    """Verify it runs a coroutine without error when a loop is already active."""
    # The presence of @pytest.mark.asyncio ensures an event loop is running.
    result = run_async_safely(sample_coroutine())
    assert result == "done"
