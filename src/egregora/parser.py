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

from .models import WhatsAppExport
from .schema import ensure_message_schema
from .zip_utils import ZipValidationError, ensure_safe_member_size, validate_zip_contents

logger = logging.getLogger(__name__)


def parse_export(export: WhatsAppExport) -> pl.DataFrame:
    """Parse an individual export into a Polars ``DataFrame``."""

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
    return ensure_message_schema(df)


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

# FIXME: This regex is complex and could be hard to understand. Add more comments to explain what it does.
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

#TODO: This function has a lot of logic for parsing dates. It could be simplified.
def _parse_message_date(token: str) -> date | None:
    normalized = token.strip()
    if not normalized:
        return None

    def _normalize(parsed: datetime) -> date:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
        return parsed.date()

    try:
        parsed_iso = date_parser.isoparse(normalized)
    except (TypeError, ValueError, OverflowError):
        parsed_iso = None
    else:
        return _normalize(parsed_iso)

    for options in _DATE_PARSE_PREFERENCES:
        try:
            parsed = date_parser.parse(normalized, **options)
        except (TypeError, ValueError, OverflowError):
            continue
        return _normalize(parsed)

    return None


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u202f", " ")
    normalized = _INVISIBLE_MARKS.sub("", normalized)
    return normalized

# TODO: This function is too long and complex. It could be split into smaller
# functions. For example, the logic for finalizing a message could be extracted
# into a separate function. The date and time parsing could also be extracted.
def _parse_messages(lines: Iterable[str], export: WhatsAppExport) -> list[dict]:  # noqa: PLR0915
    """Parse messages from an iterable of strings."""

    rows: list[dict] = []
    current_date = export.export_date
    current_message: dict | None = None

    def _finalize_current() -> None:
        nonlocal current_message
        if current_message is None:
            return

        message_lines: list[str] = current_message.pop("_message_lines", [])
        original_lines: list[str] = current_message.pop("_original_lines", [])

        message_text = "\n".join(message_lines).strip()
        original_text = "\n".join(original_lines).strip()

        current_message["message"] = message_text
        current_message["original_line"] = original_text or None
        rows.append(current_message)
        current_message = None

    for raw_line in lines:
        stripped_line = raw_line.rstrip("\n")
        normalized_line = _normalize_text(stripped_line)
        line = normalized_line.strip()
        if not line:
            if current_message is not None:
                current_message["_message_lines"].append("")
                current_message["_original_lines"].append("")
            continue

        match = _LINE_PATTERN.match(line)
        if not match:
            if current_message is not None:
                current_message["_message_lines"].append(_normalize_text(line))
                current_message["_original_lines"].append(normalized_line)
            continue

        date_str = match.group("date")
        time_str = match.group("time")
        am_pm = match.group("ampm")
        author = match.group("author")

        if date_str:
            parsed_date = _parse_message_date(date_str)
            if parsed_date:
                msg_date = parsed_date
                current_date = parsed_date
            else:
                msg_date = current_date
        else:
            msg_date = current_date

        try:
            if am_pm:
                msg_time = datetime.strptime(f"{time_str} {am_pm.upper()}", "%I:%M %p").time()
            else:
                msg_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            logger.debug("Failed to parse time '%s' in line: %s", time_str, line)
            continue

        _finalize_current()

        initial_message = _normalize_text(match.group("message").strip())
        current_message = {
            "timestamp": datetime.combine(msg_date, msg_time),
            "date": msg_date,
            "time": msg_time.strftime("%H:%M"),
            "author": _normalize_text(author.strip()),
            "message": "",
            "group_slug": export.group_slug,
            "group_name": export.group_name,
            "original_line": None,
            "tagged_line": None,
            "_message_lines": [initial_message],
            "_original_lines": [normalized_line],
        }

    _finalize_current()

    return rows


_INVISIBLE_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e]")
