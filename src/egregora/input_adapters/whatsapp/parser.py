"""WhatsApp chat parser that converts ZIP exports to Ibis Tables.

This module handles parsing of WhatsApp export files into structured data.
It automatically anonymizes all author names before returning data.

MODERN (Phase 8): Pure Ibis/DuckDB parsing without pyparsing dependency.
Uses vectorized string operations and regex instead of pyparsing grammar.

Documentation:
- Architecture: docs/guides/architecture.md
- Core Concepts: docs/getting-started/concepts.md
- API Reference: docs/reference/api.md

Consolidated (2025-11-18): Merged parser_sql.py into this file to eliminate
unnecessary module split. All parsing logic (pure Python + SQL/Ibis) now lives here.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
import zipfile
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import ibis
from dateutil import parser as date_parser

from egregora.constants import EgregoraCommand
from egregora.database.ir_schema import MESSAGE_SCHEMA
from egregora.privacy.anonymizer import anonymize_table
from egregora.privacy.uuid_namespaces import deterministic_author_uuid
from egregora.utils.zip import ZipValidationError, ensure_safe_member_size, validate_zip_contents

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ibis.expr.types import Table

    from egregora.input_adapters.whatsapp.models import WhatsAppExport

logger = logging.getLogger(__name__)

# Internal columns for tracking during parsing
_IMPORT_ORDER_COLUMN = "_import_order"
_IMPORT_SOURCE_COLUMN = "_import_source"
_AUTHOR_UUID_HEX_COLUMN = "_author_uuid_hex"

# WhatsApp message line pattern
# Matches: "28/10/2025 14:10 - Franklin: message text"
# MUST have author and colon (to match pyparsing behavior)
# Groups: (date, time, author, message)
WHATSAPP_LINE_PATTERN = re.compile(
    r"^(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})(?:,\s*|\s+)(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)\s*[—\-]\s*([^:]+):\s*(.*)$"
)

# Text normalization
_INVISIBLE_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e]")

# Command parsing constants
SET_COMMAND_PARTS = 2
EGREGORA_COMMAND_PATTERN = re.compile("^/egregora\\s+(\\w+)\\s+(.+)$", re.IGNORECASE)


# ============================================================================
# Text Normalization and Parsing Helpers
# ============================================================================


def _normalize_text(value: str) -> str:
    """Normalize unicode text."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u202f", " ")
    return _INVISIBLE_MARKS.sub("", normalized)


def _parse_message_date(token: str) -> date | None:
    """Parse date token into a date object."""
    normalized = token.strip()
    if not normalized:
        return None

    # Try ISO format first
    try:
        parsed = date_parser.isoparse(normalized)
        parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        return parsed.date()
    except (TypeError, ValueError, OverflowError):
        pass

    # Try dayfirst=True then dayfirst=False
    for dayfirst in (True, False):
        try:
            parsed = date_parser.parse(normalized, dayfirst=dayfirst)
            parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
            return parsed.date()
        except (TypeError, ValueError, OverflowError):
            continue

    return None


def _parse_message_time(time_token: str) -> datetime.time | None:
    """Parse time token into a time object (naive, for later localization)."""
    time_token = time_token.strip()

    # Check for AM/PM
    am_pm_match = re.search(r"([AaPp][Mm])$", time_token)
    if am_pm_match:
        am_pm = am_pm_match.group(1).upper()
        time_str = time_token[: am_pm_match.start()].strip()
        try:
            return datetime.strptime(f"{time_str} {am_pm}", "%I:%M %p").time()
        except ValueError:
            return None

    # 24-hour format
    try:
        return datetime.strptime(time_token, "%H:%M").time()
    except ValueError:
        return None


def _resolve_timezone(timezone: str | ZoneInfo | None) -> ZoneInfo:
    """Resolve timezone string or object to ZoneInfo."""
    if timezone is None:
        return UTC
    if isinstance(timezone, ZoneInfo):
        return timezone
    return ZoneInfo(timezone)


def _parse_messages_pure_python(
    lines: list[str], export: WhatsAppExport, timezone: str | ZoneInfo | None
) -> list[dict]:
    """Parse messages using pure Python (transitional implementation).

    This is a simplified version without pyparsing dependency.
    Uses regex instead of pyparsing grammar.
    """
    rows: list[dict] = []
    current_date = export.export_date
    current_message: dict | None = None
    position = 0
    tz = _resolve_timezone(timezone)
    tenant_id = str(export.group_slug)
    source_identifier = "whatsapp"

    for raw_line in lines:
        # Normalize line
        stripped = raw_line.rstrip("\n")
        normalized = _normalize_text(stripped)
        trimmed = normalized.strip()

        # Empty lines are added to current message
        if not trimmed:
            if current_message is not None:
                current_message["_continuation_lines"].append("")
                current_message["_original_lines"].append("")
            continue

        # Try parsing as new message line
        match = WHATSAPP_LINE_PATTERN.match(trimmed)

        if not match:
            # Not a message line - append to current message
            if current_message is not None:
                current_message["_continuation_lines"].append(trimmed)
                current_message["_original_lines"].append(normalized)
            continue

        # Finalize previous message
        if current_message is not None:
            finalized = _finalize_message(current_message, tenant_id, source_identifier)
            # Skip empty messages (WhatsApp exports occasionally include blank lines)
            # IR v1: use 'text' instead of 'message'
            if finalized and finalized["text"] and finalized["text"].strip():
                finalized[_IMPORT_ORDER_COLUMN] = position
                rows.append(finalized)
                position += 1

        # Parse new message components (regex now captures author and message directly)
        date_str = match.group(1)
        time_str = match.group(2)
        author = _normalize_text(match.group(3).strip())
        message = _normalize_text(match.group(4).strip())

        # Parse date
        msg_date = _parse_message_date(date_str)
        if msg_date:
            current_date = msg_date
        else:
            msg_date = current_date

        # Parse time
        msg_time = _parse_message_time(time_str)
        if msg_time is None:
            # Invalid time, skip this line
            continue

        # Create timestamp
        timestamp = datetime.combine(msg_date, msg_time, tzinfo=tz)

        # Start new message
        current_message = {
            "timestamp": timestamp,
            "date": msg_date,
            "author": author,
            "author_raw": author,
            "_continuation_lines": [message],
            "_original_lines": [normalized],
        }

    # Finalize last message
    if current_message is not None:
        finalized = _finalize_message(current_message, tenant_id, source_identifier)
        # Skip empty messages (WhatsApp exports occasionally include blank lines)
        # IR v1: use 'text' instead of 'message'
        if finalized and finalized["text"] and finalized["text"].strip():
            finalized[_IMPORT_ORDER_COLUMN] = position
            rows.append(finalized)

    return rows


def _finalize_message(msg: dict, tenant_id: str, source: str) -> dict:
    """Finalize a message by joining continuation lines - returns IR schema format."""
    message_text = "\n".join(msg["_continuation_lines"]).strip()
    original_text = "\n".join(msg["_original_lines"]).strip()

    author_raw = msg["author_raw"]
    author_uuid = deterministic_author_uuid(tenant_id, source, author_raw)

    # IR v1: use 'ts' and 'text' column names
    return {
        "ts": msg["timestamp"],  # IR v1: ts not timestamp
        "date": msg["date"],
        "author": author_raw,
        "author_raw": author_raw,
        "author_uuid": str(author_uuid),
        _AUTHOR_UUID_HEX_COLUMN: author_uuid.hex,
        "text": message_text,  # IR v1: text not message
        "original_line": original_text or None,
        "tagged_line": None,
    }


def _add_message_ids(messages: Table) -> Table:
    """Add deterministic message_id column based on milliseconds since group creation."""
    if int(messages.count().execute()) == 0:
        return messages

    # IR v1: use 'ts' column instead of 'timestamp'
    min_ts = messages.ts.min()
    delta_ms = ((messages.ts.epoch_seconds() - min_ts.epoch_seconds()) * 1000).round().cast("int64")

    order_columns = [messages.ts]
    if _IMPORT_SOURCE_COLUMN in messages.columns:
        order_columns.append(messages[_IMPORT_SOURCE_COLUMN])
    if _IMPORT_ORDER_COLUMN in messages.columns:
        order_columns.append(messages[_IMPORT_ORDER_COLUMN])
    # IR v1: use 'author_raw' instead of 'author'
    if "author_raw" in messages.columns:
        order_columns.append(messages.author_raw)
    elif "author" in messages.columns:
        order_columns.append(messages.author)
    # IR v1: use 'text' instead of 'message'
    if "text" in messages.columns:
        order_columns.append(messages.text)
    elif "message" in messages.columns:
        order_columns.append(messages.message)

    row_number = ibis.row_number().over(order_by=order_columns)
    return messages.mutate(message_id=delta_ms.cast("string") + "_" + row_number.cast("string"))


# ============================================================================
# Command Parsing (Egregora Commands)
# ============================================================================


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
        messages: Parsed Table with IR schema (columns: timestamp, author, text, etc.)

    Returns:
        List of command dicts:
        [{
            'author': 'a3f8c2b1',
            'timestamp': '2025-01-15 14:32:00',
            'command': {...},
            'message': 'original message text'
        }]

    """
    # IR v1: use 'text' column instead of 'message'
    normalized = messages.mutate(normalized_message=normalize_smart_quotes(messages.text))
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
            ibis.cases(
                ((enriched.action == "set") & enriched.set_has_value, ibis.literal("set")),
                (enriched.action.isin(["remove", "unset", "opt-out", "opt-in"]), enriched.action),
                else_=ibis.null(),
            )
        ),
    )

    command_cases = command_cases.mutate(
        command_target=ibis.cases(
            (command_cases.command_name == "set", command_cases.target_candidate.lower()),
            (command_cases.command_name == "remove", command_cases.args_trimmed.lower()),
            (command_cases.command_name == "unset", command_cases.args_trimmed.lower()),
            else_=ibis.null(),
        ),
        command_value=ibis.cases(
            (command_cases.command_name == "set", strip_wrapping_quotes(command_cases.value_candidate)),
            else_=ibis.null(),
        ),
    )

    # IR v1: select IR columns (text not message, author_uuid not author, ts not timestamp)
    commands_table = command_cases.filter(command_cases.command_name.notnull()).select(
        command_cases.author_uuid,
        command_cases.ts,  # IR v1: ts not timestamp
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
        if target is not None and target == target:
            command_payload["target"] = target

        value = row.get("command_value")
        if value is not None and value == value:
            command_payload["value"] = value

        commands.append(
            {
                "author": row["author_uuid"],  # IR v1: use author_uuid
                "timestamp": row["ts"],  # IR v1: use ts (not timestamp)
                "command": command_payload,
                "message": row["text"],  # IR v1: use text (not message)
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
        messages: Ibis Table with IR schema ('text' column)

    Returns:
        (filtered_table, num_removed)

    """
    # IR v1: use 'text' column instead of 'message'
    mask = messages.text.lower().startswith("/egregora")
    # Use pure Ibis (no pandas)
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


def parse_source(
    export: WhatsAppExport,
    timezone: str | ZoneInfo | None = None,
    *,
    expose_raw_author: bool = False,
) -> Table:
    """Parse WhatsApp export using pure Ibis/DuckDB operations.

    This function replaces pyparsing with vectorized SQL operations:
    1. Read all lines into table with line numbers
    2. Parse message headers with regex
    3. Group multi-line messages with window functions
    4. Aggregate continuation lines
    5. Return IR-compliant table

    Args:
        export: WhatsApp export metadata
        timezone: Timezone for timestamp normalization
        expose_raw_author: When True, keep the original WhatsApp author names in the
            returned table. Defaults to False so downstream consumers continue
            receiving anonymized author identifiers.

    Returns:
        Parsed Table conforming to MESSAGE_SCHEMA. Authors are anonymized by
        default unless ``expose_raw_author`` is set.

    """
    with zipfile.ZipFile(export.zip_path) as zf:
        validate_zip_contents(zf)
        ensure_safe_member_size(zf, export.chat_file)
        try:
            with zf.open(export.chat_file) as raw:
                text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                lines = [line.rstrip("\n") for line in text_stream]
        except UnicodeDecodeError as exc:
            msg = f"Failed to decode chat file '{export.chat_file}': {exc}"
            raise ZipValidationError(msg) from exc

    if not lines:
        logger.warning("No messages found in %s", export.zip_path)
        # IR v1: Return empty table with IR schema directly (no validation needed)
        empty_table = ibis.memtable([], schema=ibis.schema(MESSAGE_SCHEMA))
        return empty_table

    # Parse lines with pure Python (will be replaced with SQL in next step)
    rows = _parse_messages_pure_python(lines, export, timezone)

    if not rows:
        # IR v1: Return empty table with IR schema directly (no validation needed)
        empty_table = ibis.memtable([], schema=ibis.schema(MESSAGE_SCHEMA))
        return empty_table

    messages = ibis.memtable(rows)
    # IR v1: use 'ts' column instead of 'timestamp'
    if _IMPORT_ORDER_COLUMN in messages.columns:
        messages = messages.order_by([messages.ts, messages[_IMPORT_ORDER_COLUMN]])
    else:
        messages = messages.order_by("ts")

    messages = _add_message_ids(messages)

    if _IMPORT_ORDER_COLUMN in messages.columns:
        messages = messages.drop(_IMPORT_ORDER_COLUMN)

    messages = anonymize_table(messages)

    # IR v1: Drop internal helper columns, keep author_raw and author_uuid for IR schema
    helper_columns = [_AUTHOR_UUID_HEX_COLUMN]
    columns_to_drop = [col for col in helper_columns if col in messages.columns]
    if columns_to_drop:
        messages = messages.drop(*columns_to_drop)

    # IR v1: Adapter returns IR schema directly (ts, text, author_raw, author_uuid)
    return messages


def parse_multiple(
    exports: Sequence[WhatsAppExport],
    timezone: str | ZoneInfo | None = None,
    *,
    expose_raw_author: bool = False,
) -> Table:
    """Parse multiple exports and concatenate them ordered by timestamp."""
    tables: list[Table] = []

    for export in exports:
        try:
            table = parse_source(export, timezone=timezone, expose_raw_author=expose_raw_author)
            # Add import source tracking
            if table.count().execute() > 0:
                table = table.mutate(**{_IMPORT_SOURCE_COLUMN: ibis.literal(len(tables))})
                tables.append(table)
        except ZipValidationError as exc:
            logger.warning("Skipping %s due to unsafe ZIP: %s", export.zip_path.name, exc)
            continue

    if not tables:
        # IR v1: Return empty table with IR schema directly (no validation needed)
        empty_table = ibis.memtable([], schema=ibis.schema(MESSAGE_SCHEMA))
        return empty_table

    combined = tables[0]
    for table in tables[1:]:
        combined = combined.union(table, distinct=False)

    # Re-order and add message IDs
    # IR v1: use 'ts' column instead of 'timestamp'
    order_keys = [combined.ts]
    if _IMPORT_SOURCE_COLUMN in combined.columns:
        order_keys.append(combined[_IMPORT_SOURCE_COLUMN])
    combined = combined.order_by(order_keys)

    combined = _add_message_ids(combined)

    # Cleanup tracking columns
    if _IMPORT_SOURCE_COLUMN in combined.columns:
        combined = combined.drop(_IMPORT_SOURCE_COLUMN)

    # IR v1: Adapter returns IR schema directly (no validation needed)
    return combined
