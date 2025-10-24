"""WhatsApp chat parser that converts ZIP exports to Polars DataFrames."""

from __future__ import annotations

import io
import logging
import re
import unicodedata
import zipfile
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime

import polars as pl
from dateutil import parser as date_parser

from .anonymizer import anonymize_dataframe
from .models import WhatsAppExport
from .schema import ensure_message_schema
from .zip_utils import ZipValidationError, ensure_safe_member_size, validate_zip_contents

# Constants
SET_COMMAND_PARTS = 2

logger = logging.getLogger(__name__)


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


def parse_egregora_command(message: str) -> dict | None:
    """
    Parse egregora commands from message text.

    Supported commands:
    - /egregora set alias "Franklin"
    - /egregora remove alias
    - /egregora set bio "I love Python"
    - /egregora set twitter "@franklindev"
    - /egregora set website "https://franklin.dev"
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
    """
    # Normalize curly quotes to straight quotes (English only, as requested)
    # This handles copy-paste from phones/messaging apps
    message = message.replace('"', '"').replace('"', '"')
    message = message.replace("'", "'").replace("'", "'")

    # Check for simple commands first (no args)
    simple_cmd = message.strip().lower()
    if simple_cmd == "/egregora opt-out":
        return {"command": "opt-out"}
    elif simple_cmd == "/egregora opt-in":
        return {"command": "opt-in"}

    match = EGREGORA_COMMAND_PATTERN.match(message.strip())
    if not match:
        return None

    action = match.group(1).lower()
    args = match.group(2).strip()

    if action in COMMAND_REGISTRY:
        return COMMAND_REGISTRY[action](args)

    return None


def extract_commands(df: pl.DataFrame) -> list[dict]:
    """
    Extract egregora commands from parsed DataFrame.

    Commands are messages starting with /egregora that set user preferences
    like aliases, bios, links, etc.

    Args:
        df: Parsed DataFrame with columns: timestamp, author, message

    Returns:
        List of command dicts:
        [{
            'author': 'a3f8c2b1',
            'timestamp': '2025-01-15 14:32:00',
            'command': {...}
        }]
    """
    if df.is_empty():
        return []

    commands = []

    for row in df.iter_rows(named=True):
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


def filter_egregora_messages(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """
    Remove all messages starting with /egregora from DataFrame.

    This serves dual purposes:
    1. Remove command spam from content (clean posts)
    2. Allow users to mark specific messages as excluded

    Users can use /egregora prefix to exclude any message:
    - /egregora This is private, don't include
    - /egregora [sensitive discussion]
    - /egregora opt-out (command)
    - /egregora set alias "Name" (command)

    Args:
        df: Polars DataFrame with 'message' column

    Returns:
        (filtered_df, num_removed)
    """
    if df.is_empty():
        return df, 0

    original_count = len(df)

    # Filter out messages starting with /egregora (case-insensitive)
    filtered_df = df.filter(~pl.col("message").str.to_lowercase().str.starts_with("/egregora"))

    removed_count = original_count - len(filtered_df)

    if removed_count > 0:
        logger.info(f"Removed {removed_count} /egregora messages from DataFrame")

    return filtered_df, removed_count


def parse_export(export: WhatsAppExport, timezone=None) -> pl.DataFrame:
    """
    Parse an individual export into a Polars ``DataFrame``.

    Args:
        export: WhatsApp export metadata
        timezone: ZoneInfo timezone object (phone's timezone)

    Returns:
        Parsed and anonymized DataFrame with correct timezone
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
        return pl.DataFrame()

    df = pl.DataFrame(rows).sort("timestamp")
    df = ensure_message_schema(df, timezone=timezone)
    df = anonymize_dataframe(df)
    return df


def parse_multiple(exports: Sequence[WhatsAppExport]) -> pl.DataFrame:
    """Parse multiple exports and concatenate them ordered by timestamp."""

    frames: list[pl.DataFrame] = []

    for export in exports:
        try:
            df = parse_export(export)
        except ZipValidationError as exc:
            logger.warning("Skipping %s due to unsafe ZIP: %s", export.zip_path.name, exc)
            continue
        if not df.is_empty():
            frames.append(df)

    if not frames:
        return ensure_message_schema(pl.DataFrame())

    return ensure_message_schema(pl.concat(frames).sort("timestamp"))


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
            rows.append(builder.finalize())

        builder = _start_message_builder(
            export=export,
            msg_date=msg_date,
            msg_time=msg_time,
            author=_normalize_text(match.group("author").strip()),
            initial_message=_normalize_text(match.group("message").strip()),
            original_line=prepared.normalized,
        )

    if builder is not None:
        rows.append(builder.finalize())

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


def _start_message_builder(
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
        group_slug=export.group_slug,
        group_name=export.group_name,
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
        group_slug: str,
        group_name: str,
    ) -> None:
        self.timestamp = timestamp
        self.date = date
        self.author = author
        self.group_slug = group_slug
        self.group_name = group_name
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
            "time": self.timestamp.strftime("%H:%M"),
            "author": self.author,
            "message": message_text,
            "group_slug": self.group_slug,
            "group_name": self.group_name,
            "original_line": original_text or None,
            "tagged_line": None,
        }


class _PreparedLine:
    __slots__ = ("original", "normalized", "trimmed")

    def __init__(self, *, original: str, normalized: str, trimmed: str) -> None:
        self.original = original
        self.normalized = normalized
        self.trimmed = trimmed
