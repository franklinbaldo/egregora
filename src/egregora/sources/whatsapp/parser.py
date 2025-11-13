"""WhatsApp chat parser that converts ZIP exports to Ibis Tables.

This module handles parsing of WhatsApp export files into structured data.
It automatically anonymizes all author names before returning data.

MODERN (Phase 8): Pure Ibis/DuckDB parsing without pyparsing dependency.
Uses vectorized string operations and regex instead of pyparsing grammar.

Documentation:
- Architecture: docs/guides/architecture.md
- Core Concepts: docs/getting-started/concepts.md
- API Reference: docs/reference/api.md
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import ibis

from egregora.constants import EgregoraCommand
from egregora.sources.whatsapp.parser_sql import parse_multiple as _parse_multiple_impl
from egregora.sources.whatsapp.parser_sql import parse_source as _parse_source_impl

if TYPE_CHECKING:
    from collections.abc import Sequence
    from zoneinfo import ZoneInfo

    from ibis.expr.types import Table

    from egregora.sources.whatsapp.models import WhatsAppExport

SET_COMMAND_PARTS = 2
logger = logging.getLogger(__name__)
EGREGORA_COMMAND_PATTERN = re.compile("^/egregora\\s+(\\w+)\\s+(.+)$", re.IGNORECASE)


def _parse_set_command(args: str) -> dict | None:
    """Parse a 'set' command."""
    parts = args.split(maxsplit=1)
    if len(parts) == SET_COMMAND_PARTS:
        target = parts[0].lower()
        value = parts[1].strip("\"'")
        return {"command": "set", "target": target, "value": value}
    return None


def _parse_remove_command(args: str) -> dict:
    """Parse a 'remove' command."""
    return {"command": "remove", "target": args.lower(), "value": None}


COMMAND_REGISTRY = {"set": _parse_set_command, "remove": _parse_remove_command}


def parse_egregora_command(message: str) -> dict | None:
    """Parse egregora commands from message text.

    Supported commands:
    - /egregora set alias "Franklin"
    - /egregora remove alias
    - /egregora set bio "I love Python"
    - /egregora set twitter "@franklindev"
    - /egregora set website "https://franklin.dev"
    - /egregora set avatar <url>
    - /egregora set avatar (with attached image)
    - /egregora unset avatar
    - /egregora opt-out
    - /egregora opt-in

    Args:
        message: Message text to parse

    Returns:
        Command dict or None if not a command:
        {
            'command': 'set',
            'target': 'alias',
            'value': 'Franklin'
        }
        or
        {
            'command': 'opt-out'
        }
        or
        {
            'command': 'unset',
            'target': 'avatar'
        }

    """
    message = message.replace(""", '"').replace(""", '"')
    message = message.replace("'", "'").replace("'", "'")
    simple_cmd = message.strip().lower()

    # Handle simple commands with dictionary lookup
    simple_commands = {
        EgregoraCommand.OPT_OUT.value: {"command": "opt-out"},
        EgregoraCommand.OPT_IN.value: {"command": "opt-in"},
        "/egregora unset avatar": {"command": "unset", "target": "avatar", "value": None},
    }
    if simple_cmd in simple_commands:
        return simple_commands[simple_cmd]

    match = EGREGORA_COMMAND_PATTERN.match(message.strip())
    if not match:
        return None
    action = match.group(1).lower()
    args = match.group(2).strip()
    if action == "unset":
        return {"command": "unset", "target": args.lower(), "value": None}
    # Use get() with lambda to handle missing keys without additional return
    return COMMAND_REGISTRY.get(action, lambda _: None)(args)


def extract_commands(messages: Table) -> list[dict]:
    """Extract egregora commands from parsed Table.

    Commands are messages starting with /egregora that set user preferences
    like aliases, bios, links, etc.

    Args:
        messages: Parsed Table with columns: timestamp, author, message

    Returns:
        List of command dicts:
        [{
            'author': 'a3f8c2b1',
            'timestamp': '2025-01-15 14:32:00',
            'command': {...},
            'message': 'original message text'
        }]

    """
    if int(messages.count().execute()) == 0:
        return []
    commands = []
    rows = messages.execute().to_dict("records")
    for row in rows:
        message = row.get("message", "")
        if not message:
            continue
        cmd = parse_egregora_command(message)
        if cmd:
            commands.append(
                {"author": row["author"], "timestamp": row["timestamp"], "command": cmd, "message": message}
            )
    if commands:
        logger.info("Found %s egregora commands", len(commands))
    return commands


def filter_egregora_messages(messages: Table) -> tuple[Table, int]:
    """Remove all messages starting with /egregora from Table.

    This serves dual purposes:
    1. Remove command spam from content (clean posts)
    2. Allow users to mark specific messages as excluded

    Users can use /egregora prefix to exclude any message:
    - /egregora This is private, don't include
    - /egregora [sensitive discussion]
    - /egregora opt-out (command)
    - /egregora set alias "Name" (command)

    Args:
        messages: Ibis Table with 'message' column

    Returns:
        (filtered_table, num_removed)

    """
    if int(messages.count().execute()) == 0:
        return (messages, 0)
    original_count = int(messages.count().execute())
    filtered_messages = messages.filter(~messages.message.lower().startswith("/egregora"))
    removed_count = original_count - int(filtered_messages.count().execute())
    if removed_count > 0:
        logger.info("Removed %s /egregora messages from table", removed_count)
    return (filtered_messages, removed_count)


def parse_source(export: WhatsAppExport, timezone: str | ZoneInfo | None = None) -> Table:
    """Parse an individual WhatsApp export into an Ibis Table.

    Phase 8: Pure Ibis/DuckDB implementation without pyparsing.

    Args:
        export: WhatsApp export metadata
        timezone: ZoneInfo timezone object (phone's timezone)

    Returns:
        Parsed and anonymized Table with correct timezone

    """
    return _parse_source_impl(export, timezone=timezone)


def parse_multiple(exports: Sequence[WhatsAppExport], timezone: str | ZoneInfo | None = None) -> Table:
    """Parse multiple exports and concatenate them ordered by timestamp.

    Args:
        exports: Sequence of WhatsApp export metadata
        timezone: Timezone name (e.g., 'America/Sao_Paulo') or ZoneInfo object. Defaults to UTC if None.

    """
    return _parse_multiple_impl(exports, timezone=timezone)


# Note: All parsing implementation has been moved to parser_sql.py (Phase 8)
# This module now only contains command parsing and filtering utilities
