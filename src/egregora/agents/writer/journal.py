"""Journaling logic for the writer agent.

This module handles the extraction of thinking, text, and tool calls from agent messages
and saves them to a structured journal file.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.exceptions import TemplateError, TemplateNotFound
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

from egregora.agents.types import JournalEntry, JournalEntryParams
from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from egregora.data_primitives.protocols import OutputSink

logger = logging.getLogger(__name__)

# Template constants
JOURNAL_TEMPLATE_NAME = "journal.md.jinja"
TEMPLATES_DIR_NAME = "templates"

# Journal entry types
JOURNAL_TYPE_THINKING = "thinking"
JOURNAL_TYPE_TEXT = "journal"
JOURNAL_TYPE_TOOL_CALL = "tool_call"
JOURNAL_TYPE_TOOL_RETURN = "tool_return"

# Type aliases
MessageHistory = Sequence[ModelRequest | ModelResponse]


def _create_tool_call_entry(part: ToolCallPart, timestamp: datetime | None) -> JournalEntry:
    """Create a journal entry for a tool call part."""
    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
    return JournalEntry(
        JOURNAL_TYPE_TOOL_CALL,
        f"Tool: {part.tool_name}\nArguments:\n{args_str}",
        timestamp,
        part.tool_name,
    )


def _process_response_part(part: Any, timestamp: datetime | None) -> JournalEntry | None:
    """Convert a message part to a journal entry."""
    if isinstance(part, ThinkingPart):
        return JournalEntry(JOURNAL_TYPE_THINKING, part.content, timestamp)
    if isinstance(part, TextPart):
        return JournalEntry(JOURNAL_TYPE_TEXT, part.content, timestamp)
    if isinstance(part, ToolCallPart):
        return _create_tool_call_entry(part, timestamp)
    if isinstance(part, ToolReturnPart):
        result_str = str(part.content) if hasattr(part, "content") else "No result"
        return JournalEntry(
            JOURNAL_TYPE_TOOL_RETURN,
            f"Result: {result_str}",
            timestamp,
            getattr(part, "tool_name", None),
        )
    return None


def extract_intercalated_log(messages: MessageHistory) -> list[JournalEntry]:
    """Extract intercalated journal log preserving actual execution order."""
    entries: list[JournalEntry] = []

    for message in messages:
        timestamp = getattr(message, "timestamp", None)

        if isinstance(message, ModelResponse):
            entries.extend(
                filter(
                    None,
                    (_process_response_part(part, timestamp) for part in message.parts),
                )
            )

        elif isinstance(message, ModelRequest):
            entries.extend(
                _create_tool_call_entry(part, timestamp)
                for part in message.parts
                if isinstance(part, ToolCallPart)
            )

    return entries


def extract_journal_content(messages: MessageHistory) -> str:
    """Extract journal content from agent message history."""
    journal_parts: list[str] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            journal_parts.extend(part.content for part in message.parts if isinstance(part, TextPart))
    return "\n\n".join(journal_parts).strip()


def save_journal_to_file(params: JournalEntryParams) -> str | None:
    """Save journal entry to markdown file."""
    intercalated_log = params.intercalated_log
    if not intercalated_log:
        return None

    # Resolve templates dir relative to the package structure
    # This module is src/egregora/agents/writer/journal.py
    # Templates are in src/egregora/templates
    # So we need to go up 2 levels (agents, then egregora) to find templates inside egregora
    # Actually, parents[0] is writer, parents[1] is agents, parents[2] is egregora.
    templates_dir = Path(__file__).resolve().parents[2] / TEMPLATES_DIR_NAME

    now_utc = datetime.now(tz=UTC)
    window_start_iso = params.window_start.astimezone(UTC).isoformat()
    window_end_iso = params.window_end.astimezone(UTC).isoformat()
    journal_slug = now_utc.strftime("%Y-%m-%d-%H-%M-%S")

    try:
        # Security: Enable autoescape for markdown/jinja templates to prevent XSS in journals
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "htm", "xml", "jinja", "md"]),
        )
        template = env.get_template(JOURNAL_TEMPLATE_NAME)
        journal_content = template.render(
            window_label=params.window_label,
            date=now_utc.strftime("%Y-%m-%d"),
            created=now_utc.isoformat(),
            posts_published=params.posts_published,
            profiles_updated=params.profiles_updated,
            entry_count=len(intercalated_log),
            intercalated_log=intercalated_log,
            window_start=window_start_iso,
            window_end=window_end_iso,
            total_tokens=params.total_tokens,
        )

        doc = Document(
            content=journal_content,
            type=DocumentType.JOURNAL,
            metadata={
                "window_label": params.window_label,
                "window_start": window_start_iso,
                "window_end": window_end_iso,
                "date": now_utc.strftime("%Y-%m-%d %H:%M"),
                "created_at": now_utc.strftime("%Y-%m-%d %H:%M"),
                "slug": journal_slug,
                "nav_exclude": True,
                "hide": ["navigation"],
            },
            source_window=params.window_label,
        )
        params.output_format.persist(doc)
        logger.info("Saved journal entry: %s", doc.document_id)
    except (TemplateNotFound, TemplateError):
        logger.exception("Journal template error")
    except (OSError, PermissionError):
        logger.exception("File system error during journal creation")
    except (TypeError, AttributeError):
        logger.exception("Invalid data for journal")
    except ValueError:
        logger.exception("Invalid journal document")
    else:
        return doc.document_id
    return None
