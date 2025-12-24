"""Tests for async utilities."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from egregora.utils.async_utils import run_async_safely


async def sample_coroutine() -> str:
    """A simple coroutine for testing."""
    await asyncio.sleep(0.01)
    return "done"


@pytest.mark.asyncio
async def test_run_async_safely_with_running_loop():
    """Verify run_async_safely works correctly when an event loop is already running."""
    # The test is already running in an event loop thanks to pytest-asyncio
    result = run_async_safely(sample_coroutine())
    assert result == "done"


def test_run_async_safely_without_running_loop():
    """Verify run_async_safely works correctly when no event loop is running."""
    # This test runs outside of the pytest-asyncio event loop context
    result = run_async_safely(sample_coroutine())
    assert result == "done"


def test_run_async_safely_handles_runtime_error_gracefully():
    """Verify run_async_safely falls back to asyncio.run when get_running_loop fails."""
    with patch("asyncio.get_running_loop", side_effect=RuntimeError):
        with patch("asyncio.run") as mock_run:
            run_async_safely(sample_coroutine())
            mock_run.assert_called_once()
