"""Handles parsing and filtering of /egregora commands from WhatsApp messages.

This module is responsible for identifying, parsing, and extracting commands
(e.g., `/egregora set alias "My Name"`) from the raw message text. It also
provides utilities to filter these command messages out of the main conversation
table, ensuring they don't appear in the final generated content.

Key Functions:
- `parse_egregora_command`: Parses a single message string into a command dict.
- `extract_commands`: Iterates over a message table to find all commands.
- `filter_egregora_messages`: Removes command messages from a table.
"""

import logging
import re
from typing import TYPE_CHECKING

from egregora.constants import EgregoraCommand

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)

# Command constants
CMD_PREFIX = "/egregora"
CMD_SET = "set"
CMD_REMOVE = "remove"
CMD_UNSET = "unset"
CMD_OPT_OUT = "opt-out"
CMD_OPT_IN = "opt-in"

# Regex for complex commands like /egregora set <target> <value>
EGREGORA_COMMAND_PATTERN = re.compile(f"^{CMD_PREFIX}\\s+(\\w+)\\s+(.+)$", re.IGNORECASE)
SET_COMMAND_PARTS = 2


def _parse_set_command(args: str) -> dict | None:
    """Parse a 'set' command's arguments."""
    parts = args.split(maxsplit=1)
    if len(parts) == SET_COMMAND_PARTS:
        target = parts[0].lower()
        value = parts[1].strip("\"'")
        return {"command": CMD_SET, "target": target, "value": value}
    return None


def _parse_remove_command(args: str) -> dict:
    """Parse a 'remove' command's arguments."""
    return {"command": CMD_REMOVE, "target": args.lower(), "value": None}


def _parse_unset_command(args: str) -> dict:
    """Parse an 'unset' command's arguments."""
    return {"command": CMD_UNSET, "target": args.lower(), "value": None}


COMMAND_PARSERS = {
    CMD_SET: _parse_set_command,
    CMD_REMOVE: _parse_remove_command,
    CMD_UNSET: _parse_unset_command,
}


def _normalize_message(message: str) -> str:
    """Normalize quotes for consistent parsing."""
    return message.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")


def _handle_simple_commands(normalized_message: str) -> dict | None:
    """Handle simple, argument-less commands."""
    simple_cmd = normalized_message.strip().lower()
    simple_commands = {
        EgregoraCommand.OPT_OUT.value: {"command": CMD_OPT_OUT},
        EgregoraCommand.OPT_IN.value: {"command": CMD_OPT_IN},
        f"{CMD_PREFIX} {CMD_UNSET} avatar": {"command": CMD_UNSET, "target": "avatar", "value": None},
    }
    return simple_commands.get(simple_cmd)


def parse_egregora_command(message: str) -> dict | None:
    """Parse egregora commands from message text."""
    normalized_message = _normalize_message(message)
    if simple_command := _handle_simple_commands(normalized_message):
        return simple_command
    match = EGREGORA_COMMAND_PATTERN.match(normalized_message.strip())
    if not match:
        return None
    action = match.group(1).lower()
    args = match.group(2).strip()
    parser = COMMAND_PARSERS.get(action)
    if parser:
        return parser(args)
    return None


def extract_commands(messages: "Table") -> list[dict]:
    """Extract egregora commands from a parsed Table."""
    if messages.count().execute() == 0:
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


def filter_egregora_messages(messages: "Table") -> tuple["Table", int]:
    """Remove all messages starting with /egregora from a Table (IR v1: uses 'text' column)."""
    if messages.count().execute() == 0:
        return messages, 0
    original_count = int(messages.count().execute())
    # IR v1: use 'text' column instead of 'message'
    filtered_messages = messages.filter(~messages.text.lower().startswith(CMD_PREFIX))
    removed_count = original_count - int(filtered_messages.count().execute())
    if removed_count > 0:
        logger.info("Removed %s /egregora messages from table", removed_count)
    return filtered_messages, removed_count
