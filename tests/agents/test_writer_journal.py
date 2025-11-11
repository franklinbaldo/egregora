"""Unit tests for writer agent journal functionality."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic_ai.messages import (
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

from egregora.agents.writer.agent import (
    JournalEntry,
    _extract_freeform_content,
    _extract_intercalated_log,
    _extract_thinking_content,
    _save_journal_to_file,
)
from tests.helpers.storage import InMemoryJournalStorage


def test_extract_thinking_content_empty():
    """Test thinking extraction with no messages."""
    messages: list = []
    result = _extract_thinking_content(messages)
    assert result == []


def test_extract_thinking_content_single():
    """Test thinking extraction with single ThinkingPart."""
    messages = [
        ModelResponse(
            parts=[ThinkingPart(content="Let me analyze this step by step...")],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )
    ]
    result = _extract_thinking_content(messages)
    assert len(result) == 1
    assert result[0] == "Let me analyze this step by step..."


def test_extract_thinking_content_multiple():
    """Test thinking extraction with multiple ThinkingParts."""
    messages = [
        ModelResponse(
            parts=[ThinkingPart(content="Step 1: Identify themes...")],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        ),
        ModelResponse(
            parts=[ThinkingPart(content="Step 2: Synthesize content...")],
            timestamp=datetime(2025, 1, 15, 10, 1, tzinfo=UTC),
        ),
    ]
    result = _extract_thinking_content(messages)
    assert len(result) == 2
    assert result[0] == "Step 1: Identify themes..."
    assert result[1] == "Step 2: Synthesize content..."


def test_extract_thinking_content_mixed_parts():
    """Test thinking extraction ignores non-ThinkingParts."""
    messages = [
        ModelResponse(
            parts=[
                ThinkingPart(content="Thinking content..."),
                TextPart(content="Freeform content..."),
            ],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )
    ]
    result = _extract_thinking_content(messages)
    assert len(result) == 1
    assert result[0] == "Thinking content..."


def test_extract_freeform_content_empty():
    """Test freeform extraction with no messages."""
    messages: list = []
    result = _extract_freeform_content(messages)
    assert result == ""


def test_extract_freeform_content_single():
    """Test freeform extraction with single TextPart."""
    messages = [
        ModelResponse(
            parts=[TextPart(content="This is a reflection on the conversation...")],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )
    ]
    result = _extract_freeform_content(messages)
    assert result == "This is a reflection on the conversation..."


def test_extract_freeform_content_multiple():
    """Test freeform extraction joins multiple TextParts."""
    messages = [
        ModelResponse(
            parts=[TextPart(content="First reflection...")],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        ),
        ModelResponse(
            parts=[TextPart(content="Second reflection...")],
            timestamp=datetime(2025, 1, 15, 10, 1, tzinfo=UTC),
        ),
    ]
    result = _extract_freeform_content(messages)
    assert result == "First reflection...\n\nSecond reflection..."


def test_extract_freeform_content_mixed_parts():
    """Test freeform extraction ignores non-TextParts."""
    messages = [
        ModelResponse(
            parts=[
                ThinkingPart(content="Thinking content..."),
                TextPart(content="Freeform content..."),
            ],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )
    ]
    result = _extract_freeform_content(messages)
    assert result == "Freeform content..."


def test_extract_intercalated_log_empty():
    """Test intercalated log extraction with no messages."""
    messages: list = []
    result = _extract_intercalated_log(messages)
    assert result == []


def test_extract_intercalated_log_thinking_only():
    """Test intercalated log with only thinking content."""
    messages = [
        ModelResponse(
            parts=[ThinkingPart(content="Analyzing...")],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )
    ]
    result = _extract_intercalated_log(messages)
    assert len(result) == 1
    assert result[0].entry_type == "thinking"
    assert result[0].content == "Analyzing..."
    assert result[0].timestamp == datetime(2025, 1, 15, 10, 0, tzinfo=UTC)


def test_extract_intercalated_log_freeform_only():
    """Test intercalated log with only freeform content."""
    messages = [
        ModelResponse(
            parts=[TextPart(content="Reflection...")],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )
    ]
    result = _extract_intercalated_log(messages)
    assert len(result) == 1
    assert result[0].entry_type == "freeform"
    assert result[0].content == "Reflection..."


def test_extract_intercalated_log_with_tool_calls():
    """Test intercalated log preserves tool call order."""
    messages = [
        ModelResponse(
            parts=[
                ThinkingPart(content="I need to write a post..."),
                ToolCallPart(tool_name="write_post", args={"title": "Test Post", "content": "Content here"}),
            ],
            timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        ),
        ModelResponse(
            parts=[
                ToolReturnPart(
                    content='{"status": "success", "path": "/posts/test.md"}', tool_name="write_post"
                )
            ],
            timestamp=datetime(2025, 1, 15, 10, 1, tzinfo=UTC),
        ),
        ModelResponse(
            parts=[TextPart(content="Post created successfully.")],
            timestamp=datetime(2025, 1, 15, 10, 2, tzinfo=UTC),
        ),
    ]
    result = _extract_intercalated_log(messages)
    assert len(result) == 4
    # Check order
    assert result[0].entry_type == "thinking"
    assert "I need to write a post..." in result[0].content
    assert result[1].entry_type == "tool_call"
    assert result[1].tool_name == "write_post"
    assert "write_post" in result[1].content
    assert result[2].entry_type == "tool_return"
    assert "success" in result[2].content
    assert result[3].entry_type == "freeform"
    assert "Post created successfully." in result[3].content


def test_extract_intercalated_log_preserves_chronological_order():
    """Test intercalated log maintains chronological execution order."""
    messages = [
        ModelResponse(
            parts=[ThinkingPart(content="First thought")], timestamp=datetime(2025, 1, 15, 10, 0, tzinfo=UTC)
        ),
        ModelResponse(
            parts=[TextPart(content="First text")], timestamp=datetime(2025, 1, 15, 10, 1, tzinfo=UTC)
        ),
        ModelResponse(
            parts=[ThinkingPart(content="Second thought")], timestamp=datetime(2025, 1, 15, 10, 2, tzinfo=UTC)
        ),
        ModelResponse(
            parts=[TextPart(content="Second text")], timestamp=datetime(2025, 1, 15, 10, 3, tzinfo=UTC)
        ),
    ]
    result = _extract_intercalated_log(messages)
    assert len(result) == 4
    # Verify chronological order
    assert result[0].content == "First thought"
    assert result[1].content == "First text"
    assert result[2].content == "Second thought"
    assert result[3].content == "Second text"


def test_save_journal_to_file_empty_log(tmp_path: Path):
    """Test journal saving with empty log returns None."""
    journals = InMemoryJournalStorage()

    result = _save_journal_to_file([], "2025-01-15 10:00 to 12:00", journals)
    assert result is None


def test_save_journal_to_file_creates_directory(tmp_path: Path):
    """Test journal saving with in-memory storage."""
    journals = InMemoryJournalStorage()

    log = [JournalEntry(entry_type="thinking", content="Test thinking")]
    result = _save_journal_to_file(log, "2025-01-15 10:00 to 12:00", journals)

    assert result is not None
    # Verify journal was stored
    content = journals.get_by_label("2025-01-15 10:00 to 12:00")
    assert content is not None
    assert "Test thinking" in content


def test_save_journal_to_file_sanitizes_filename(tmp_path: Path):
    """Test journal saving sanitizes window label in identifier."""
    journals = InMemoryJournalStorage()

    log = [JournalEntry(entry_type="thinking", content="Test")]
    result = _save_journal_to_file(log, "2025-01-15 10:00 to 12:00", journals)

    assert result is not None
    # Identifier should have sanitized label (colons→hyphens, spaces→underscores)
    assert result == "memory://journal/2025-01-15_10-00_to_12-00"


def test_save_journal_to_file_contains_frontmatter(tmp_path: Path):
    """Test journal file contains YAML frontmatter."""
    journals = InMemoryJournalStorage()

    log = [JournalEntry(entry_type="thinking", content="Test content")]
    result = _save_journal_to_file(log, "2025-01-15 10:00 to 12:00", journals)
    assert result is not None

    # Retrieve the content from in-memory storage
    content = journals.get_by_label("2025-01-15 10:00 to 12:00")
    assert content is not None
    # Check frontmatter
    assert "---" in content
    assert "window_label: 2025-01-15 10:00 to 12:00" in content
    assert "draft: true" in content
    assert "date:" in content
    assert "created:" in content


def test_save_journal_to_file_missing_templates_dir(tmp_path: Path):
    """Test journal saving uses built-in template when custom templates don't exist."""
    journals = InMemoryJournalStorage()

    log = [JournalEntry(entry_type="thinking", content="Test")]
    # Should succeed using built-in template from package
    result = _save_journal_to_file(log, "2025-01-15 10:00 to 12:00", journals)
    assert result is not None  # Built-in template always available


def test_journal_entry_frozen():
    """Test JournalEntry is frozen (immutable)."""
    entry = JournalEntry(entry_type="thinking", content="Test")

    with pytest.raises(FrozenInstanceError):
        entry.content = "Modified"  # type: ignore[misc]
