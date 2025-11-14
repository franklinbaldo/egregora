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
from egregora.input_adapters.whatsapp.parser_sql import parse_multiple as _parse_multiple_impl
from egregora.input_adapters.whatsapp.parser_sql import parse_source as _parse_source_impl

if TYPE_CHECKING:
    from collections.abc import Sequence
    from zoneinfo import ZoneInfo

    from ibis.expr.types import Table

    from egregora.input_adapters.whatsapp.models import WhatsAppExport

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

SMART_QUOTES_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)


@ibis.udf.scalar.python
def normalize_smart_quotes(value: str | None) -> str:
    """Normalize smart quotes in command text for vectorized parsing."""
    if value is None:
        return ""
    return value.translate(SMART_QUOTES_TRANSLATION)


@ibis.udf.scalar.python
def strip_wrapping_quotes(value: str | None) -> str | None:
    """Strip wrapping single/double quotes from string values."""
    if value is None:
        return None
    return value.strip("\"'")


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

    Smart quotes are normalized to their ASCII equivalents before parsing, so
    commands like `/egregora set alias “Franklin”` or `/egregora set alias ‘Franklin’`
    are accepted.

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
    message = message.translate(SMART_QUOTES_TRANSLATION)
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
    normalized = messages.mutate(normalized_message=normalize_smart_quotes(messages.message))
    filtered = normalized.filter(normalized.normalized_message.lower().startswith("/egregora"))

    trimmed = filtered.mutate(trimmed_message=filtered.normalized_message.strip())

    parsed = trimmed.mutate(
        action=trimmed.trimmed_message.re_extract(r"^/egregora\s+([^\s]+)", 1).lower(),
        args_raw=trimmed.trimmed_message.re_extract(r"^/egregora\s+[^\s]+\s*(.*)$", 1),
    )

    enriched = parsed.mutate(
        args_trimmed=ibis.coalesce(parsed.args_raw, ibis.literal("")),
    )
    enriched = enriched.mutate(
        args_trimmed=enriched.args_trimmed.strip(),
    )

    enriched = enriched.mutate(
        target_candidate=enriched.args_trimmed.re_extract(r"^([^\s]+)", 1),
        value_candidate=enriched.args_trimmed.re_extract(r"^[^\s]+\s*(.*)$", 1),
    )

    enriched = enriched.mutate(
        set_has_value=ibis.coalesce(
            enriched.args_trimmed.length()
            > ibis.coalesce(enriched.target_candidate.length(), ibis.literal(0)),
            ibis.literal(False),
        ),
    )

    command_cases = enriched.mutate(
        command_name=(
            ibis.case()
            .when((enriched.action == "set") & enriched.set_has_value, ibis.literal("set"))
            .when(enriched.action.isin(["remove", "unset", "opt-out", "opt-in"]), enriched.action)
            .else_(ibis.null())
            .end()
        ),
    )

    command_cases = command_cases.mutate(
        command_target=(
            ibis.case()
            .when(command_cases.command_name == "set", command_cases.target_candidate.lower())
            .when(command_cases.command_name == "remove", command_cases.args_trimmed.lower())
            .when(command_cases.command_name == "unset", command_cases.args_trimmed.lower())
            .else_(ibis.null())
            .end()
        ),
        command_value=(
            ibis.case()
            .when(command_cases.command_name == "set", strip_wrapping_quotes(command_cases.value_candidate))
            .else_(ibis.null())
            .end()
        ),
    )

    commands_table = command_cases.filter(command_cases.command_name.notnull()).select(
        command_cases.author,
        command_cases.timestamp,
        command_cases.message,
        command_cases.command_name,
        command_cases.command_target,
        command_cases.command_value,
    )

    result_df = commands_table.execute()
    if result_df.empty:
        return []

    commands: list[dict] = []
    for row in result_df.to_dict(orient="records"):
        command_payload = {"command": row["command_name"]}

        target = row.get("command_target")
        if target is not None and target == target:
            command_payload["target"] = target

        value = row.get("command_value")
        if value is not None and value == value:
            command_payload["value"] = value

        commands.append(
            {
                "author": row["author"],
                "timestamp": row["timestamp"],
                "command": command_payload,
                "message": row["message"],
            }
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
    mask = messages.message.lower().startswith("/egregora")
    counts_df = messages.aggregate(
        original_count=messages.count(),
        removed_count=mask.sum(),
    ).execute()
    counts_row = counts_df.iloc[0]
    original_count = int(counts_row.get("original_count", 0) or 0)
    if original_count == 0:
        return (messages, 0)
    removed_count = int(counts_row.get("removed_count", 0) or 0)
    # IR v1 schema exposes the conversation text in the `message` column
    filtered_messages = messages.filter(~mask)
    if removed_count > 0:
        logger.info("Removed %s /egregora messages from table", removed_count)
    return (filtered_messages, removed_count)


def parse_source(
    export: WhatsAppExport,
    timezone: str | ZoneInfo | None = None,
    *,
    expose_raw_author: bool = False,
) -> Table:
    """Parse an individual WhatsApp export into an Ibis Table.

    Phase 8: Pure Ibis/DuckDB implementation without pyparsing.

    Args:
        export: WhatsApp export metadata
        timezone: ZoneInfo timezone object (phone's timezone)
        expose_raw_author: When True, keep original author names for downstream
            processing (e.g., IR generation). Defaults to False so callers
            receive anonymized identifiers.

    Returns:
        Parsed Table with correct timezone. Authors remain anonymized unless
        ``expose_raw_author`` is requested.

    """
    return _parse_source_impl(export, timezone=timezone, expose_raw_author=expose_raw_author)


def parse_multiple(
    exports: Sequence[WhatsAppExport],
    timezone: str | ZoneInfo | None = None,
    *,
    expose_raw_author: bool = False,
) -> Table:
    """Parse multiple exports and concatenate them ordered by timestamp.

    Args:
        exports: Sequence of WhatsApp export metadata
        timezone: Timezone name (e.g., 'America/Sao_Paulo') or ZoneInfo object. Defaults to UTC if None.

    """
    return _parse_multiple_impl(
        exports,
        timezone=timezone,
        expose_raw_author=expose_raw_author,
    )


# Note: All parsing implementation has been moved to parser_sql.py (Phase 8)
# This module now only contains command parsing and filtering utilities
