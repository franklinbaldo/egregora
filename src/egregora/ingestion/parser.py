"""WhatsApp chat parser that converts ZIP exports to Ibis Tables.

This module handles parsing of WhatsApp export files into structured data.
It automatically anonymizes all author names before returning data.

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
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime

import ibis
from dateutil import parser as date_parser
from ibis.expr.types import Table

from ..core.models import WhatsAppExport
from ..core.schema import MESSAGE_SCHEMA, ensure_message_schema
from ..privacy.anonymizer import anonymize_table
from ..utils.zip import ZipValidationError, ensure_safe_member_size, validate_zip_contents

# Constants
SET_COMMAND_PARTS = 2

logger = logging.getLogger(__name__)

_IMPORT_ORDER_COLUMN = "_import_order"
_IMPORT_SOURCE_COLUMN = "_import_source"

# Pattern for egregora commands: /egregora <command> <args>
EGREGORA_COMMAND_PATTERN = re.compile(r"^/egregora\s+(\w+)\s+(.+)$", re.IGNORECASE)


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


COMMAND_REGISTRY = {
    "set": _parse_set_command,
    "remove": _parse_remove_command,
}


def parse_egregora_command(message: str) -> dict | None:  # noqa: PLR0911
    """
    Parse egregora commands from message text.

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
    # Normalize curly quotes to straight quotes (English only, as requested)
    # This handles copy-paste from phones/messaging apps
    message = message.replace(""", '"').replace(""", '"')
    message = message.replace("'", "'").replace("'", "'")

    # Check for simple commands first (no args)
    simple_cmd = message.strip().lower()
    if simple_cmd == "/egregora opt-out":
        return {"command": "opt-out"}
    elif simple_cmd == "/egregora opt-in":
        return {"command": "opt-in"}
    elif simple_cmd == "/egregora unset avatar":
        return {"command": "unset", "target": "avatar", "value": None}

    match = EGREGORA_COMMAND_PATTERN.match(message.strip())
    if not match:
        return None

    action = match.group(1).lower()
    args = match.group(2).strip()

    # Special handling for "unset" as an alias for "remove"
    if action == "unset":
        return {"command": "unset", "target": args.lower(), "value": None}

    if action in COMMAND_REGISTRY:
        return COMMAND_REGISTRY[action](args)

    return None


def extract_commands(messages: Table) -> list[dict]:
    """
    Extract egregora commands from parsed Table.

    Commands are messages starting with /egregora that set user preferences
    like aliases, bios, links, etc.

    Args:
        messages: Parsed Table with columns: timestamp, author, message

    Returns:
        List of command dicts:
        [{
            'author': 'a3f8c2b1',
            'timestamp': '2025-01-15 14:32:00',
            'command': {...}
        }]
    """
    if int(messages.count().execute()) == 0:
        return []

    commands = []

    # Convert to pandas for iteration (most efficient for small result sets)
    rows = messages.execute().to_dict("records")

    for row in rows:
        message = row.get("message", "")
        if not message:
            continue

        cmd = parse_egregora_command(message)
        if cmd:
            commands.append(
                {"author": row["author"], "timestamp": row["timestamp"], "command": cmd}
            )

    if commands:
        logger.info(f"Found {len(commands)} egregora commands")

    return commands


def _add_message_ids(messages: Table) -> Table:
    """
    Add deterministic message_id column based on milliseconds since group creation.

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

    # Calculate milliseconds since first message using relative time deltas
    # We keep min_timestamp as an Ibis expression (not executed) so the entire
    # calculation happens in the database query. This ensures consistent timezone
    # handling and avoids issues with different timezone interpretations.
    min_timestamp = messages.timestamp.min()

    # Calculate the time difference from minimum timestamp to each message timestamp
    # epoch_seconds() converts both to seconds since epoch, then we subtract to get delta
    # The delta is timezone-independent because both timestamps use the same timezone
    # Multiply by 1000 to convert seconds to milliseconds, round to ensure integer
    delta_ms = (
        ((messages.timestamp.epoch_seconds() - min_timestamp.epoch_seconds()) * 1000)
        .round()
        .cast("int64")
    )

    # Add row number for uniqueness (0-indexed)
    # Explicit ordering ensures deterministic IDs even if the backend reorders rows
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

    messages_with_id = messages.mutate(
        message_id=(delta_ms.cast("string") + "_" + row_number.cast("string"))
    )

    return messages_with_id


def filter_egregora_messages(messages: Table) -> tuple[Table, int]:
    """
    Remove all messages starting with /egregora from Table.

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
    total_messages = int(messages.count().execute())
    if total_messages == 0:
        return messages, 0

    # Filter out messages starting with /egregora (case-insensitive)
    filtered_messages = messages.filter(~messages.message.lower().startswith("/egregora"))

    removed_count = total_messages - int(filtered_messages.count().execute())
    if int(messages.count().execute()) == 0:
        return messages, 0

    original_count = int(messages.count().execute())

    # Filter out messages starting with /egregora (case-insensitive)
    filtered_messages = messages.filter(~messages.message.lower().startswith("/egregora"))

    removed_count = original_count - int(filtered_messages.count().execute())

    if removed_count > 0:
        logger.info(f"Removed {removed_count} /egregora messages from table")

    return filtered_messages, removed_count


def parse_export(export: WhatsAppExport, timezone=None) -> Table:
    """
    Parse an individual export into an Ibis ``Table``.

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
                rows = _parse_messages(text_stream, export)
        except UnicodeDecodeError as exc:
            raise ZipValidationError(
                f"Failed to decode chat file '{export.chat_file}': {exc}"
            ) from exc

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
    messages = anonymize_table(messages)
    return messages


def parse_multiple(exports: Sequence[WhatsAppExport]) -> Table:  # noqa: PLR0912
    """Parse multiple exports and concatenate them ordered by timestamp."""

    tables: list[Table] = []

    for export in exports:
        try:
            # Parse without adding message IDs yet - we'll do it globally
            with zipfile.ZipFile(export.zip_path) as zf:
                validate_zip_contents(zf)
                ensure_safe_member_size(zf, export.chat_file)

                try:
                    with zf.open(export.chat_file) as raw:
                        text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                        rows = _parse_messages(text_stream, export)
                except UnicodeDecodeError as exc:
                    raise ZipValidationError(
                        f"Failed to decode chat file '{export.chat_file}': {exc}"
                    ) from exc

            if rows:
                for row in rows:
                    row[_IMPORT_SOURCE_COLUMN] = len(tables)

                messages = ibis.memtable(rows)
                if _IMPORT_ORDER_COLUMN in messages.columns:
                    messages = messages.order_by(
                        [messages.timestamp, messages[_IMPORT_ORDER_COLUMN]]
                    )
                else:
                    messages = messages.order_by("timestamp")

                tables.append(messages)
        except ZipValidationError as exc:
            logger.warning("Skipping %s due to unsafe ZIP: %s", export.zip_path.name, exc)
            continue

    if not tables:
        empty_table = ibis.memtable([], schema=ibis.schema(MESSAGE_SCHEMA))
        return ensure_message_schema(empty_table)

    # Concatenate all frames using union
    combined = tables[0]
    for table in tables[1:]:
        combined = combined.union(table, distinct=False)

    # Order by timestamp first, then add message IDs globally
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

    combined = ensure_message_schema(combined)
    combined = anonymize_table(combined)

    return combined


# Pattern captures optional date, mandatory time, separator (dash/en dash),
# author, and the message content. WhatsApp exports vary the separator and may
# include date prefixes (DD/MM/YYYY or locale variants) as well as AM/PM markers.
_LINE_PATTERN = re.compile(
    r"^("
    r"(?:(?P<date>\d{1,2}/\d{1,2}/\d{2,4})(?:,\s*|\s+))?"
    r"(?P<time>\d{1,2}:\d{2})"
    r"(?:\s*(?P<ampm>[APap][Mm]))?"
    r"\s*[—\-]\s*"
    r"(?P<author>[^:]+?):\s*"
    r"(?P<message>.+)"
    r")$"
)


_DATE_PARSE_PREFERENCES: tuple[dict[str, bool], ...] = (
    {"dayfirst": True},
    {"dayfirst": False},
)


def _parse_message_date(token: str) -> date | None:
    """Parse ``token`` into a ``date`` in UTC, returning ``None`` when invalid."""

    normalized = token.strip()
    if not normalized:
        return None

    parsed = _parse_iso_date(normalized) or _parse_with_preferences(normalized)
    if parsed is None:
        return None
    return _normalise_parsed_date(parsed)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u202f", " ")
    normalized = _INVISIBLE_MARKS.sub("", normalized)
    return normalized


def _parse_messages(lines: Iterable[str], export: WhatsAppExport) -> list[dict]:
    """Parse messages from an iterable of strings."""

    rows: list[dict] = []
    current_date = export.export_date
    builder: _MessageBuilder | None = None
    position = 0

    for raw_line in lines:
        prepared = _prepare_line(raw_line)
        if prepared.trimmed == "":
            if builder is not None:
                builder.append("", "")
            continue

        match = _LINE_PATTERN.match(prepared.trimmed)
        if not match:
            if builder is not None:
                builder.append(_normalize_text(prepared.trimmed), prepared.normalized)
            continue

        msg_date, current_date = _resolve_message_date(match.group("date"), current_date)
        msg_time = _parse_message_time(match.group("time"), match.group("ampm"), prepared.trimmed)
        if msg_time is None:
            continue

        if builder is not None:
            row = builder.finalize()
            row[_IMPORT_ORDER_COLUMN] = position
            rows.append(row)
            position += 1

        builder = _start_message_builder(
            export=export,
            msg_date=msg_date,
            msg_time=msg_time,
            author=_normalize_text(match.group("author").strip()),
            initial_message=_normalize_text(match.group("message").strip()),
            original_line=prepared.normalized,
        )

    if builder is not None:
        row = builder.finalize()
        row[_IMPORT_ORDER_COLUMN] = position
        rows.append(row)

    return rows


_INVISIBLE_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e]")


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
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    return parsed.date()


def _prepare_line(raw_line: str) -> _PreparedLine:
    stripped = raw_line.rstrip("\n")
    normalized = _normalize_text(stripped)
    return _PreparedLine(original=stripped, normalized=normalized, trimmed=normalized.strip())


def _resolve_message_date(date_token: str | None, fallback: date) -> tuple[date, date]:
    if not date_token:
        return fallback, fallback

    parsed = _parse_message_date(date_token)
    if parsed is None:
        return fallback, fallback
    return parsed, parsed


def _parse_message_time(time_token: str, am_pm: str | None, context_line: str):
    try:
        if am_pm:
            return datetime.strptime(f"{time_token} {am_pm.upper()}", "%I:%M %p").time()
        return datetime.strptime(time_token, "%H:%M").time()
    except ValueError:
        logger.debug("Failed to parse time '%s' in line: %s", time_token, context_line)
        return None


def _start_message_builder(  # noqa: PLR0913
    *,
    export: WhatsAppExport,
    msg_date: date,
    msg_time,
    author: str,
    initial_message: str,
    original_line: str,
) -> _MessageBuilder:
    builder = _MessageBuilder(
        timestamp=datetime.combine(msg_date, msg_time),
        date=msg_date,
        author=author,
    )
    builder.append(initial_message, original_line)
    return builder


class _MessageBuilder:
    """Incrementally assemble a message entry before committing to ``rows``."""

    def __init__(
        self,
        *,
        timestamp: datetime,
        date: date,
        author: str,
    ) -> None:
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
    __slots__ = ("original", "normalized", "trimmed")

    def __init__(self, *, original: str, normalized: str, trimmed: str) -> None:
        self.original = original
        self.normalized = normalized
        self.trimmed = trimmed
