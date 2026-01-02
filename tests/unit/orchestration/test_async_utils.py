
import asyncio
import pytest
from egregora.orchestration.async_utils import run_async_safely

# A simple async function to use in tests
async def sample_coroutine(value):
    await asyncio.sleep(0.01)
    return f"Coroutine completed with value: {value}"

def test_run_async_safely_without_running_loop():
    """
    Tests that run_async_safely works correctly when no event loop is running.
    """
    test_value = "no_loop"
    result = run_async_safely(sample_coroutine(test_value))
    assert result == f"Coroutine completed with value: {test_value}"

@pytest.mark.asyncio
async def test_run_async_safely_with_running_loop():
    """
    Tests that run_async_safely works correctly when an event loop is already running.
    This test itself runs in an event loop provided by pytest-asyncio.
    """
    test_value = "with_loop"
    # Inside this async test, an event loop is already running.
    result = run_async_safely(sample_coroutine(test_value))
    assert result == f"Coroutine completed with value: {test_value}"

# Another test to be absolutely sure about the running loop case
@pytest.mark.asyncio
async def test_nested_run_async_safely():
    """
    Tests nesting calls to run_async_safely within a running event loop.
    """
    async def outer_coroutine():
        inner_result = run_async_safely(sample_coroutine("inner"))
        return f"Outer received: ({inner_result})"

    # The outer_coroutine is called from an already running loop (from the test)
    # and it calls run_async_safely again.
    result = await outer_coroutine()
    assert result == "Outer received: (Coroutine completed with value: inner)"
