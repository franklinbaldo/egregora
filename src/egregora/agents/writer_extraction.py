"""Extraction utilities for the Writer agent.

This module handles parsing and extracting structured data from Pydantic-AI message history,
including tool results, thinking traces, and journal content.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

# Constants for Journal entry types
JOURNAL_TYPE_THINKING = "thinking"
JOURNAL_TYPE_TEXT = "journal"
JOURNAL_TYPE_TOOL_CALL = "tool_call"
JOURNAL_TYPE_TOOL_RETURN = "tool_return"

MessageHistory = Sequence[ModelRequest | ModelResponse]


@dataclass(frozen=True)
class JournalEntry:
    """Represents a single entry in the intercalated journal log."""

    entry_type: str  # "thinking", "journal", "tool_call", "tool_return"
    content: str
    timestamp: datetime | None = None
    tool_name: str | None = None


def create_tool_call_entry(part: ToolCallPart, timestamp: datetime | None) -> JournalEntry:
    """Create a journal entry for a tool call part.

    Args:
        part: Tool call part from message
        timestamp: Message timestamp

    Returns:
        Journal entry for the tool call

    """
    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
    return JournalEntry(
        JOURNAL_TYPE_TOOL_CALL,
        f"Tool: {part.tool_name}\nArguments:\n{args_str}",
        timestamp,
        part.tool_name,
    )


def extract_thinking_content(messages: MessageHistory) -> list[str]:
    """Extract thinking/reasoning content from agent message history."""
    thinking_contents: list[str] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            thinking_contents.extend(part.content for part in message.parts if isinstance(part, ThinkingPart))
    return thinking_contents


def extract_journal_content(messages: MessageHistory) -> str:
    """Extract journal content from agent message history."""
    journal_parts: list[str] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            journal_parts.extend(part.content for part in message.parts if isinstance(part, TextPart))
    return "\n\n".join(journal_parts).strip()


def extract_intercalated_log(messages: MessageHistory) -> list[JournalEntry]:
    """Extract intercalated journal log preserving actual execution order."""
    entries: list[JournalEntry] = []

    for message in messages:
        timestamp = getattr(message, "timestamp", None)

        # Handle ModelResponse
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ThinkingPart):
                    entries.append(JournalEntry(JOURNAL_TYPE_THINKING, part.content, timestamp))
                elif isinstance(part, TextPart):
                    entries.append(JournalEntry(JOURNAL_TYPE_TEXT, part.content, timestamp))
                elif isinstance(part, ToolCallPart):
                    entries.append(create_tool_call_entry(part, timestamp))
                elif isinstance(part, ToolReturnPart):
                    result_str = str(part.content) if hasattr(part, "content") else "No result"
                    entries.append(
                        JournalEntry(
                            JOURNAL_TYPE_TOOL_RETURN,
                            f"Result: {result_str}",
                            timestamp,
                            getattr(part, "tool_name", None),
                        )
                    )

        # Handle ModelRequest
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    entries.append(create_tool_call_entry(part, timestamp))

    return entries


def extract_tool_results(messages: MessageHistory) -> tuple[list[str], list[str]]:  # noqa: C901
    """Extract saved post and profile document IDs from agent message history."""
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    def _process_result(content: Any, tool_name: str | None) -> None:
        if isinstance(content, str):
            try:
                data = json.loads(content)
            except (ValueError, json.JSONDecodeError):
                return
        elif hasattr(content, "model_dump"):
            data = content.model_dump()
        elif isinstance(content, dict):
            data = content
        else:
            return

        if data.get("status") in ("success", "scheduled") and "path" in data:
            path = data["path"]
            if tool_name == "write_post_tool" or "/posts/" in path:
                saved_posts.append(path)
            elif tool_name == "write_profile_tool" or "/profiles/" in path:
                saved_profiles.append(path)

    for message in messages:
        if hasattr(message, "parts"):
            for part in message.parts:
                if isinstance(part, ToolReturnPart):
                    _process_result(part.content, part.tool_name)
        elif hasattr(message, "kind") and message.kind == "tool-return":
            _process_result(message.content, getattr(message, "tool_name", None))

    return saved_posts, saved_profiles
