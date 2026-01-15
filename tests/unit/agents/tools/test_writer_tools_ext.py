"""Extended unit tests for writer agent tool implementations."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from egregora.agents.tools.writer_tools import ToolContext, write_post_impl


@pytest.fixture
def mock_tool_context() -> ToolContext:
    """Provides a mocked ToolContext for testing."""
    mock_output_sink = MagicMock()
    mock_output_sink.persist.return_value = None
    return ToolContext(
        output_sink=mock_output_sink,
        window_label="test_window",
        task_store=MagicMock(),
    )


def test_write_post_impl_with_json_string_metadata(mock_tool_context):
    """Verify write_post_impl correctly handles metadata as a JSON string."""
    metadata = {"title": "Test Post", "author": "Test Author"}
    metadata_json = json.dumps(metadata)
    content = "This is a test post."

    result = write_post_impl(mock_tool_context, metadata_json, content)

    assert result.status == "success"
    mock_tool_context.output_sink.persist.assert_called_once()
    persisted_doc = mock_tool_context.output_sink.persist.call_args[0][0]
    assert persisted_doc.metadata["title"] == "Test Post"
    assert persisted_doc.content == content
