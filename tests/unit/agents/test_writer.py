"""Tests for the writer agent."""

from unittest.mock import MagicMock

import pytest

from egregora.agents.types import WriterDeps
from egregora.agents.writer import _execute_writer_with_error_handling


def test_writer_module_imports():
    """Test that the writer module can be imported."""
    from egregora.agents.writer import write_posts_for_window

    assert write_posts_for_window is not None


def test_execute_writer_with_error_handling_raises_specific_exception(monkeypatch):
    """Test that _execute_writer_with_error_handling raises RuntimeError on agent failure."""
    # Arrange
    mock_inner_agent = MagicMock(side_effect=ValueError("Internal agent error"))
    monkeypatch.setattr("egregora.agents.writer.write_posts_with_pydantic_agent", mock_inner_agent)

    mock_config = MagicMock()
    mock_deps = MagicMock(spec=WriterDeps)
    mock_deps.window_label = "test-window-label"

    # Act & Assert
    with pytest.raises(RuntimeError) as exc_info:
        _execute_writer_with_error_handling(
            prompt="test prompt",
            config=mock_config,
            deps=mock_deps,
        )

    # Assert exception message contains window label
    assert "Non-recoverable writer agent failure for test-window-label" in str(exc_info.value)
