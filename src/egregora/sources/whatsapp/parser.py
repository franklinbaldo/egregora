"""WhatsApp chat parser that converts ZIP exports to Ibis Tables.

This module handles parsing of WhatsApp export files into structured data.
It automatically anonymizes all author names before returning data.

MODERN (Phase 5): Uses pyparsing grammar instead of regex patterns.

Documentation:
- Architecture: docs/guides/architecture.md
- Core Concepts: docs/getting-started/concepts.md
- API Reference: docs/reference/api.md
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
from egregora.privacy.anonymizer import anonymize_table
from egregora.sources.whatsapp.grammar import parse_whatsapp_line
from egregora.schema import MESSAGE_SCHEMA, ensure_message_schema
from egregora.utils.zip import ZipValidationError, ensure_safe_member_size, validate_zip_contents

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ibis.expr.types import Table

    from egregora.sources.whatsapp.models import WhatsAppExport

SET_COMMAND_PARTS = 2
logger = logging.getLogger(__name__)
_IMPORT_ORDER_COLUMN = "_import_order"
_IMPORT_SOURCE_COLUMN = "_import_source"
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
    if simple_cmd == EgregoraCommand.OPT_OUT.value:
        return {"command": "opt-out"}
    if simple_cmd == EgregoraCommand.OPT_IN.value:
        return {"command": "opt-in"}
    if simple_cmd == "/egregora unset avatar":
        return {"command": "unset", "target": "avatar", "value": None}
    match = EGREGORA_COMMAND_PATTERN.match(message.strip())
    if not match:
        return None
    action = match.group(1).lower()
    args = match.group(2).strip()
    if action == "unset":
        return {"command": "unset", "target": args.lower(), "value": None}
    if action in COMMAND_REGISTRY:
        return COMMAND_REGISTRY[action](args)
    return None


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


def _add_message_ids(messages: Table) -> Table:
    """Add deterministic message_id column based on milliseconds since group creation.

    The message_id combines two components:
    1. Time delta in milliseconds from first message (timezone-independent)
    2. Row number within that timestamp (for uniqueness)

    Format: "{delta_ms}_{row_num}"

    This ensures:
    - Idempotence: same group from different timezone exports produces same IDs
    - Uniqueness: multiple messages in same minute (same timestamp) get unique IDs
    - Order preservation: row numbers maintain message order within same minute

    WhatsApp exports only have minute-level precision, so multiple messages
    sent in the same minute have identical timestamps. The row number disambiguates them.

    Args:
        messages: Ibis Table with 'timestamp' column (must be pre-sorted by timestamp)

    Returns:
        Table with added 'message_id' column containing "{delta_ms}_{row_num}"

    """
    if int(messages.count().execute()) == 0:
        return messages
    min_timestamp = messages.timestamp.min()
    delta_ms = (
        ((messages.timestamp.epoch_seconds() - min_timestamp.epoch_seconds()) * 1000).round().cast("int64")
    )
    order_columns = [messages.timestamp]
    if _IMPORT_SOURCE_COLUMN in messages.columns:
        order_columns.append(messages[_IMPORT_SOURCE_COLUMN])
    if _IMPORT_ORDER_COLUMN in messages.columns:
        order_columns.append(messages[_IMPORT_ORDER_COLUMN])
    if "author" in messages.columns:
        order_columns.append(messages.author)
    if "message" in messages.columns:
        order_columns.append(messages.message)
    row_number = ibis.row_number().over(order_by=order_columns)
    return messages.mutate(message_id=delta_ms.cast("string") + "_" + row_number.cast("string"))


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


def parse_export(export: WhatsAppExport, timezone: str | ZoneInfo | None = None) -> Table:
    """Parse an individual export into an Ibis ``Table``.

    Args:
        export: WhatsApp export metadata
        timezone: ZoneInfo timezone object (phone's timezone)

    Returns:
        Parsed and anonymized Table with correct timezone

    """
    with zipfile.ZipFile(export.zip_path) as zf:
        validate_zip_contents(zf)
        ensure_safe_member_size(zf, export.chat_file)
        try:
            with zf.open(export.chat_file) as raw:
                text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                rows = _parse_messages(text_stream, export, timezone)
        except UnicodeDecodeError as exc:
            msg = f"Failed to decode chat file '{export.chat_file}': {exc}"
            raise ZipValidationError(msg) from exc
    if not rows:
        logger.warning("No messages found in %s", export.zip_path)
        empty_table = ibis.memtable([], schema=ibis.schema(MESSAGE_SCHEMA))
        return ensure_message_schema(empty_table, timezone=timezone)
    messages = ibis.memtable(rows)
    if _IMPORT_ORDER_COLUMN in messages.columns:
        messages = messages.order_by([messages.timestamp, messages[_IMPORT_ORDER_COLUMN]])
    else:
        messages = messages.order_by("timestamp")
    messages = _add_message_ids(messages)
    if _IMPORT_ORDER_COLUMN in messages.columns:
        messages = messages.drop(_IMPORT_ORDER_COLUMN)
    messages = ensure_message_schema(messages, timezone=timezone)
    return anonymize_table(messages)


def parse_multiple(exports: Sequence[WhatsAppExport], timezone: str | ZoneInfo | None = None) -> Table:
    """Parse multiple exports and concatenate them ordered by timestamp.

    Args:
        exports: Sequence of WhatsApp export metadata
        timezone: Timezone name (e.g., 'America/Sao_Paulo') or ZoneInfo object. Defaults to UTC if None.

    """
    tables: list[Table] = []
    for export in exports:
        try:
            with zipfile.ZipFile(export.zip_path) as zf:
                validate_zip_contents(zf)
                ensure_safe_member_size(zf, export.chat_file)
                try:
                    with zf.open(export.chat_file) as raw:
                        text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                        rows = _parse_messages(text_stream, export, timezone)
                except UnicodeDecodeError as exc:
                    msg = f"Failed to decode chat file '{export.chat_file}': {exc}"
                    raise ZipValidationError(msg) from exc
            if rows:
                for row in rows:
                    row[_IMPORT_SOURCE_COLUMN] = len(tables)
                messages = ibis.memtable(rows)
                if _IMPORT_ORDER_COLUMN in messages.columns:
                    messages = messages.order_by([messages.timestamp, messages[_IMPORT_ORDER_COLUMN]])
                else:
                    messages = messages.order_by("timestamp")
                tables.append(messages)
        except ZipValidationError as exc:
            logger.warning("Skipping %s due to unsafe ZIP: %s", export.zip_path.name, exc)
            continue
    if not tables:
        empty_table = ibis.memtable([], schema=ibis.schema(MESSAGE_SCHEMA))
        return ensure_message_schema(empty_table, timezone=timezone)
    combined = tables[0]
    for table in tables[1:]:
        combined = combined.union(table, distinct=False)
    if _IMPORT_ORDER_COLUMN in combined.columns or _IMPORT_SOURCE_COLUMN in combined.columns:
        order_keys = [combined.timestamp]
        if _IMPORT_SOURCE_COLUMN in combined.columns:
            order_keys.append(combined[_IMPORT_SOURCE_COLUMN])
        if _IMPORT_ORDER_COLUMN in combined.columns:
            order_keys.append(combined[_IMPORT_ORDER_COLUMN])
        combined = combined.order_by(order_keys)
    else:
        combined = combined.order_by("timestamp")
    combined = _add_message_ids(combined)
    drop_columns: list[str] = []
    if _IMPORT_ORDER_COLUMN in combined.columns:
        drop_columns.append(_IMPORT_ORDER_COLUMN)
    if _IMPORT_SOURCE_COLUMN in combined.columns:
        drop_columns.append(_IMPORT_SOURCE_COLUMN)
    if drop_columns:
        combined = combined.drop(*drop_columns)
    combined = ensure_message_schema(combined, timezone=timezone)
    return anonymize_table(combined)


# Date parsing utilities (used by grammar parser)
_DATE_PARSE_PREFERENCES: tuple[dict[str, bool], ...] = ({"dayfirst": True}, {"dayfirst": False})


def _parse_message_date(token: str) -> date | None:
    """Parse ``token`` into a ``date`` in UTC, returning ``None`` when invalid."""
    normalized = token.strip()
    if not normalized:
        return None
    parsed = _parse_iso_date(normalized) or _parse_with_preferences(normalized)
    if parsed is None:
        return None
    return _normalise_parsed_date(parsed)


def _parse_iso_date(value: str) -> datetime | None:
    try:
        return date_parser.isoparse(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _parse_with_preferences(value: str) -> datetime | None:
    for options in _DATE_PARSE_PREFERENCES:
        try:
            return date_parser.parse(value, **options)
        except (TypeError, ValueError, OverflowError):
            continue
    return None


def _normalise_parsed_date(parsed: datetime) -> date:
    parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return parsed.date()


def _parse_message_time(time_token: str, am_pm: str | None, context_line: str) -> datetime.time | None:
    """Parse time from WhatsApp message line.

    Returns naive time objects intentionally - downstream code (ensure_message_schema)
    expects naive times to properly localize them to the phone's actual timezone.
    Adding tzinfo here would cause incorrect double-conversion.
    """
    try:
        if am_pm:
            return datetime.strptime(f"{time_token} {am_pm.upper()}", "%I:%M %p").time()
        return datetime.strptime(time_token, "%H:%M").time()
    except ValueError:
        logger.debug("Failed to parse time '%s' in line: %s", time_token, context_line)
        return None


# Text normalization
_INVISIBLE_MARKS = re.compile("[\\u200e\\u200f\\u202a-\\u202e]")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u202f", " ")
    return _INVISIBLE_MARKS.sub("", normalized)


def _prepare_line(raw_line: str) -> _PreparedLine:
    stripped = raw_line.rstrip("\n")
    normalized = _normalize_text(stripped)
    return _PreparedLine(original=stripped, normalized=normalized, trimmed=normalized.strip())


def _resolve_message_date(date_token: str | None, fallback: date) -> tuple[date, date]:
    if not date_token:
        return (fallback, fallback)
    parsed = _parse_message_date(date_token)
    if parsed is None:
        return (fallback, fallback)
    return (parsed, parsed)


def _parse_messages(
    lines: Iterable[str], export: WhatsAppExport, timezone: str | ZoneInfo | None = None
) -> list[dict]:
    """Parse messages from an iterable of strings.

    Uses pyparsing grammar for declarative message line parsing.

    Args:
        lines: Iterable of message lines
        export: WhatsApp export metadata
        timezone: Timezone name (e.g., 'America/Sao_Paulo') or ZoneInfo object. Defaults to UTC if None.

    """
    rows: list[dict] = []
    current_date = export.export_date
    builder: _MessageBuilder | None = None
    position = 0

    for raw_line in lines:
        prepared = _prepare_line(raw_line)

        # Empty lines are added to current message
        if prepared.trimmed == "":
            if builder is not None:
                builder.append("", "")
            continue

        # Try parsing as new message using pyparsing grammar
        parsed = parse_whatsapp_line(prepared.trimmed)

        # Not a message line - append to current message
        if not parsed:
            if builder is not None:
                builder.append(_normalize_text(prepared.trimmed), prepared.normalized)
            continue

        # Extract parsed components
        msg_date, current_date = _resolve_message_date(parsed.get("date"), current_date)
        msg_time = _parse_message_time(parsed["time"], parsed.get("ampm"), prepared.trimmed)

        if msg_time is None:
            continue

        # Finalize previous message
        if builder is not None:
            row = builder.finalize()
            row[_IMPORT_ORDER_COLUMN] = position
            rows.append(row)
            position += 1

        # Start new message
        builder = _start_message_builder(
            _export=export,
            msg_date=msg_date,
            msg_time=msg_time,
            author=_normalize_text(parsed["author"].strip()),
            initial_message=_normalize_text(parsed["message"].strip()),
            original_line=prepared.normalized,
            timezone=timezone,
        )

    # Finalize last message
    if builder is not None:
        row = builder.finalize()
        row[_IMPORT_ORDER_COLUMN] = position
        rows.append(row)

    return rows


def _start_message_builder(
    *,
    _export: WhatsAppExport,
    msg_date: date,
    msg_time: datetime.time | None,
    author: str,
    initial_message: str,
    original_line: str,
    timezone: str | ZoneInfo | None = None,
) -> _MessageBuilder:
    if timezone is None:
        tz = UTC
    elif isinstance(timezone, ZoneInfo):
        tz = timezone
    else:
        tz = ZoneInfo(timezone)
    timestamp = datetime.combine(msg_date, msg_time, tzinfo=tz)
    builder = _MessageBuilder(timestamp=timestamp, date=msg_date, author=author)
    builder.append(initial_message, original_line)
    return builder


class _MessageBuilder:
    """Incrementally assemble a message entry before committing to ``rows``."""

    def __init__(self, *, timestamp: datetime, date: date, author: str) -> None:
        self.timestamp = timestamp
        self.date = date
        self.author = author
        self._message_lines: list[str] = []
        self._original_lines: list[str] = []

    def append(self, content: str, original: str) -> None:
        self._message_lines.append(content)
        self._original_lines.append(original)

    def finalize(self) -> dict:
        message_text = "\n".join(self._message_lines).strip()
        original_text = "\n".join(self._original_lines).strip()
        return {
            "timestamp": self.timestamp,
            "date": self.date,
            "author": self.author,
            "message": message_text,
            "original_line": original_text or None,
            "tagged_line": None,
        }


class _PreparedLine:
    __slots__ = ("normalized", "original", "trimmed")

    def __init__(self, *, original: str, normalized: str, trimmed: str) -> None:
        self.original = original
        self.normalized = normalized
        self.trimmed = trimmed
