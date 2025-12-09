"""Command extraction and filtering for WhatsApp messages."""

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING, Any

import ibis
import ibis.expr.datatypes as dt

if TYPE_CHECKING:  # pragma: no cover - for type checkers
    from ibis.expr.types import Table

# Command parsing constants
SET_COMMAND_PARTS = 2
EGREGORA_COMMAND_PATTERN = re.compile("^/egregora\\s+(\\w+)\\s+(.+)$", re.IGNORECASE)

# Regex patterns for command extraction
_COMMAND_ACTION_PATTERN = r"^/egregora\s+([^\s]+)"
_COMMAND_ARGS_PATTERN = r"^/egregora\s+[^\s]+\s*(.*)$"
_FIRST_ARG_PATTERN = r"^([^\s]+)"
_REMAINING_ARGS_PATTERN = r"^[^\s]+\s*(.*)$"


def _parse_set_command(args: str) -> dict | None:
    parts = args.split(maxsplit=1)
    if len(parts) == SET_COMMAND_PARTS:
        target = parts[0].lower()
        value = parts[1].strip("\"'")
        return {"command": "set", "target": target, "value": value}
    return None


def _parse_remove_command(args: str) -> dict:
    return {"command": "remove", "target": args.lower(), "value": None}


COMMAND_REGISTRY = {"set": _parse_set_command, "remove": _parse_remove_command}


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and math.isnan(value)


SMART_QUOTES_TRANSLATION = str.maketrans(
    {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
)

logger = logging.getLogger(__name__)


@ibis.udf.scalar.python
def normalize_smart_quotes(value: str | None) -> str:
    if value is None:
        return ""
    return value.translate(SMART_QUOTES_TRANSLATION)


@ibis.udf.scalar.python
def strip_wrapping_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip("\"'")


@ibis.udf.scalar.python
def _normalize_whitespace(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def extract_commands(messages: Table) -> list[dict]:
    """Extract egregora commands from parsed Table."""
    normalized = messages.mutate(normalized_message=normalize_smart_quotes(messages.text))
    filtered = normalized.filter(normalized.normalized_message.lower().startswith("/egregora"))
    trimmed = filtered.mutate(trimmed_message=_normalize_whitespace(filtered.normalized_message))

    parsed = trimmed.mutate(
        action=trimmed.trimmed_message.re_extract(_COMMAND_ACTION_PATTERN, 1).lower(),
        args_raw=trimmed.trimmed_message.re_extract(_COMMAND_ARGS_PATTERN, 1),
    )

    enriched = parsed.mutate(
        args_trimmed=ibis.coalesce(parsed.args_raw, ibis.literal("")).strip(),
    )

    enriched = enriched.mutate(
        target_candidate=enriched.args_trimmed.re_extract(_FIRST_ARG_PATTERN, 1),
        value_candidate=enriched.args_trimmed.re_extract(_REMAINING_ARGS_PATTERN, 1),
    )

    enriched = enriched.mutate(
        set_has_value=ibis.coalesce(
            enriched.args_trimmed.length()
            > ibis.coalesce(enriched.target_candidate.length(), ibis.literal(0)),
            ibis.literal(value=False),
        ),
    )

    command_cases = enriched.mutate(
        command_name=ibis.ifelse(
            (enriched.action == "set") & enriched.set_has_value,
            ibis.literal("set"),
            ibis.ifelse(
                enriched.action.isin(["remove", "unset", "opt-out", "opt-in"]),
                enriched.action,
                ibis.null(),
            ),
        ),
    )

    command_cases = command_cases.mutate(
        command_target=ibis.ifelse(
            command_cases.command_name == "set",
            command_cases.target_candidate.lower(),
            ibis.ifelse(
                command_cases.command_name == "remove",
                command_cases.args_trimmed.lower(),
                ibis.ifelse(
                    command_cases.command_name == "unset",
                    command_cases.args_trimmed.lower(),
                    ibis.null(),
                ),
            ),
        ),
        command_value=ibis.ifelse(
            command_cases.command_name == "set",
            strip_wrapping_quotes(command_cases.value_candidate),
            ibis.null(),
        ),
    )

    commands_table = command_cases.filter(command_cases.command_name.notnull()).select(
        command_cases.author_uuid,
        command_cases.ts,
        command_cases.text,
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
        if target is not None and not _is_nan(target):
            command_payload["target"] = target

        value = row.get("command_value")
        if value is not None and not _is_nan(value):
            command_payload["value"] = value

        commands.append(
            {
                "author": row["author_uuid"],
                "timestamp": row["ts"],
                "command": command_payload,
                "message": row["text"],
            }
        )

    if commands:
        logger.info("Found %s egregora commands", len(commands))
    return commands


def filter_egregora_messages(messages: Table) -> tuple[Table, int]:
    """Remove all messages starting with /egregora from Table."""
    mask = messages.text.lower().startswith("/egregora")
    counts = messages.aggregate(
        original_count=messages.count(),
        removed_count=mask.sum(),
    ).execute()
    original_count = int(counts["original_count"][0] or 0)
    if original_count == 0:
        return (messages, 0)
    removed_count = int(counts["removed_count"][0] or 0)
    filtered_messages = messages.filter(~mask)
    if removed_count > 0:
        logger.info("Removed %s /egregora messages from table", removed_count)
    return (filtered_messages, removed_count)
