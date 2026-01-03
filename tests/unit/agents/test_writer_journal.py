"""Tests for the writer journal utilities."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

from egregora.agents.writer_journal import (
    JournalEntry,
    JournalEntryParams,
    extract_intercalated_log,
    extract_journal_content,
    extract_thinking_content,
    save_journal_to_file,
)
from egregora.data_primitives.document import DocumentType


@pytest.fixture
def mock_output_sink():
    return MagicMock()


@pytest.fixture
def sample_messages():
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    # 1. User request (usually implicit in agent run, but here represent history)
    # 2. Model response with thinking and tool call
    response1 = ModelResponse(
        parts=[
            ThinkingPart(content="Thinking about the task..."),
            TextPart(content="I will call a tool."),
            ToolCallPart(tool_name="test_tool", args={"arg": "value"}),
        ],
        timestamp=timestamp,
    )

    # 3. Model request (tool return) - technically ModelRequest contains the tool return in pydantic-ai structure
    # but let's follow the types used in extraction functions.
    # Wait, extract_intercalated_log handles ModelRequest as containing ToolCallPart?
    # Let's check implementation of extract_intercalated_log.
    # It says:
    # elif isinstance(message, ModelRequest):
    #     entries.extend(_create_tool_call_entry(part, timestamp) for part in message.parts if isinstance(part, ToolCallPart))
    # This implies ModelRequest contains ToolCalls? Usually ModelResponse contains ToolCalls.
    # Let's verify pydantic-ai behavior or just test what the code expects.
    # The code expects ToolCallPart in ModelRequest OR ModelResponse?
    # In _extract_intercalated_log:
    # if isinstance(message, ModelResponse): process response parts (Thinking, Text, ToolCall, ToolReturn)
    # elif isinstance(message, ModelRequest): process ToolCallPart

    # Let's create a history that exercises these paths.

    return [response1]


def test_extract_thinking_content(sample_messages):
    content = extract_thinking_content(sample_messages)
    assert len(content) == 1
    assert content[0] == "Thinking about the task..."


def test_extract_journal_content(sample_messages):
    content = extract_journal_content(sample_messages)
    assert content == "I will call a tool."


def test_extract_intercalated_log(sample_messages):
    entries = extract_intercalated_log(sample_messages)
    assert len(entries) == 3

    assert entries[0].entry_type == "thinking"
    assert entries[0].content == "Thinking about the task..."

    assert entries[1].entry_type == "journal"
    assert entries[1].content == "I will call a tool."

    assert entries[2].entry_type == "tool_call"
    assert entries[2].tool_name == "test_tool"
    assert "value" in entries[2].content


def test_save_journal_to_file_success(mock_output_sink):
    params = JournalEntryParams(
        intercalated_log=[JournalEntry("journal", "content")],
        window_label="test_window",
        output_format=mock_output_sink,
        posts_published=1,
        profiles_updated=0,
        window_start=datetime.now(UTC),
        window_end=datetime.now(UTC),
    )

    # Mock Jinja2 environment to avoid loading real templates which might fail in isolated test
    with patch("egregora.agents.writer_journal.Environment") as mock_env_cls:
        mock_env = mock_env_cls.return_value
        mock_template = mock_env.get_template.return_value
        mock_template.render.return_value = "# Journal\n\nContent"

        doc_id = save_journal_to_file(params)

        # Verify persistence
        mock_output_sink.persist.assert_called_once()
        doc = mock_output_sink.persist.call_args[0][0]
        assert doc.type == DocumentType.JOURNAL
        assert doc.content == "# Journal\n\nContent"
        assert doc.metadata["window_label"] == "test_window"


def test_save_journal_to_file_empty_log(mock_output_sink):
    params = JournalEntryParams(
        intercalated_log=[],
        window_label="test_window",
        output_format=mock_output_sink,
        posts_published=0,
        profiles_updated=0,
        window_start=datetime.now(UTC),
        window_end=datetime.now(UTC),
    )

    result = save_journal_to_file(params)
    assert result is None
    mock_output_sink.persist.assert_not_called()
