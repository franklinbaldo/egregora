"""Tests for the writer agent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from egregora.agents.exceptions import AgentExecutionError
from egregora.agents.types import WriterDeps
from egregora.agents.writer import _execute_writer_with_error_handling


def test_writer_module_imports():
    """Test that the writer module can be imported."""
    from egregora.agents.writer import write_posts_for_window

    assert write_posts_for_window is not None


@pytest.mark.asyncio
async def test_execute_writer_with_error_handling_raises_specific_exception(monkeypatch):
    """Test that _execute_writer_with_error_handling raises a specific exception."""
    # Arrange
    mock_inner_agent = AsyncMock(side_effect=ValueError("Internal agent error"))
    monkeypatch.setattr("egregora.agents.writer.write_posts_with_pydantic_agent", mock_inner_agent)

    mock_config = MagicMock()
    mock_deps = MagicMock(spec=WriterDeps)
    mock_deps.window_label = "test-window-label"

    # Act & Assert
    with pytest.raises(AgentExecutionError) as exc_info:
        await _execute_writer_with_error_handling(
            prompt="test prompt",
            config=mock_config,
            deps=mock_deps,
        )

    # Assert exception details
    assert exc_info.value.window_label == "test-window-label"
    assert "Agent execution failed for window 'test-window-label': Internal agent error" in str(exc_info.value)
