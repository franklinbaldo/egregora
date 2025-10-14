"""Declarative WhatsApp ingestion helpers for the refactored pipeline."""

from __future__ import annotations

import io
import logging
import re
import unicodedata
import zipfile
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
from dateutil import parser as date_parser

from ..models import WhatsAppExport
from ..schema import ensure_message_schema
from ..zip_utils import ZipValidationError, ensure_safe_member_size, validate_zip_contents

logger = logging.getLogger(__name__)

__all__ = [
    "parse_export",
    "parse_multiple",
    "parse_zip",
    "parse_exports_lazy",
    "load_export_from_zip",
]


def parse_export(export: WhatsAppExport) -> pl.DataFrame:
    """Parse an individual export into a Polars ``DataFrame`` ready for enrichment."""

    frame = _parse_export_messages(export)
    return _ensure_ingest_columns(frame)


def parse_multiple(exports: Sequence[WhatsAppExport]) -> pl.DataFrame:
    """Parse multiple exports and concatenate them ordered by timestamp."""

    frames: list[pl.DataFrame] = []

    for export in exports:
        try:
            frame = parse_export(export)
        except ZipValidationError as exc:
            logger.warning("Skipping %s due to unsafe ZIP: %s", export.zip_path.name, exc)
            continue
        if not frame.is_empty():
            frames.append(frame)

    if not frames:
        return _ensure_ingest_columns(pl.DataFrame())

    return _ensure_ingest_columns(pl.concat(frames).sort("timestamp"))


def parse_exports_lazy(exports: Sequence[WhatsAppExport]) -> pl.LazyFrame:
    """Parse exports into a ``LazyFrame`` to ease Ibis/DuckDB interoperability."""

    return parse_multiple(exports).lazy()


def parse_zip(
    zip_path: Path,
    *,
    chat_filename: str | None = None,
    group_name: str | None = None,
    group_slug: str | None = None,
    export_date: date | None = None,
) -> pl.DataFrame:
    """Parse ``zip_path`` directly without constructing :class:`WhatsAppExport`."""

    export = load_export_from_zip(
        zip_path,
        chat_filename=chat_filename,
        group_name=group_name,
        group_slug=group_slug,
        export_date=export_date,
    )
    return parse_export(export)


def load_export_from_zip(
    zip_path: Path,
    *,
    chat_filename: str | None = None,
    group_name: str | None = None,
    group_slug: str | None = None,
    export_date: date | None = None,
) -> WhatsAppExport:
    """Create a :class:`WhatsAppExport` instance from a ZIP archive."""

    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zipped:
        validate_zip_contents(zipped)

        chat_candidates = [
            info.filename
            for info in zipped.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".txt")
        ]
        if not chat_candidates:
            msg = f"No WhatsApp transcript found inside {zip_path}"
            raise ZipValidationError(msg)

        resolved_chat = chat_filename or chat_candidates[0]
        ensure_safe_member_size(zipped, resolved_chat)

        media_files = [
            info.filename
            for info in zipped.infolist()
            if not info.is_dir() and info.filename != resolved_chat
        ]

    resolved_group_name = group_name or _extract_group_name_from_chat_file(resolved_chat)
    resolved_group_slug = group_slug or _generate_group_slug(resolved_group_name)
    resolved_date = export_date or date.today()

    return WhatsAppExport(
        zip_path=zip_path,
        group_name=resolved_group_name,
        group_slug=resolved_group_slug,
        export_date=resolved_date,
        chat_file=resolved_chat,
        media_files=media_files,
    )


def _parse_export_messages(export: WhatsAppExport) -> pl.DataFrame:
    with zipfile.ZipFile(export.zip_path) as zf:
        validate_zip_contents(zf)
        ensure_safe_member_size(zf, export.chat_file)

        try:
            with zf.open(export.chat_file) as raw:
                text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                rows = _parse_messages(text_stream, export)
        except UnicodeDecodeError as exc:
            raise ZipValidationError(
                f"Failed to decode chat file '{export.chat_file}': {exc}"  # noqa: EM101
            ) from exc

    if not rows:
        logger.warning("No messages found in %s", export.zip_path)
        return pl.DataFrame()

    return pl.DataFrame(rows).sort("timestamp")


_LINE_PATTERN = re.compile(
    r"^(?:"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})"
    r"(?:,\s*|\s+)"
    r")?"
    r"(?P<time>\d{1,2}:\d{2})"
    r"(?:\s*(?P<ampm>[APap][Mm]))?"
    r"\s*[—\-]\s*"
    r"(?P<author>[^:]+?):\s*"
    r"(?P<message>.+)$"
)

_DATE_PARSE_PREFERENCES: tuple[dict[str, bool], ...] = (
    {"dayfirst": True},
    {"dayfirst": False},
)

_INVISIBLE_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e]")


def _parse_messages(lines: Iterable[str], export: WhatsAppExport) -> list[dict]:
    """Parse messages from an iterable of strings."""

    rows: list[dict] = []
    current_date = export.export_date

    for raw_line in lines:
        normalized_line = _normalize_text(raw_line)
        line = normalized_line.strip()
        if not line:
            continue

        match = _LINE_PATTERN.match(line)
        if not match:
            continue

        date_str = match.group("date")
        time_str = match.group("time")
        am_pm = match.group("ampm")
        author = match.group("author")
        message = match.group("message")

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

        rows.append(
            {
                "timestamp": datetime.combine(msg_date, msg_time),
                "date": msg_date,
                "time": msg_time.strftime("%H:%M"),
                "author": _normalize_text(author.strip()),
                "message": _normalize_text(message.strip()),
                "group_slug": export.group_slug,
                "group_name": export.group_name,
                "original_line": line,
                "tagged_line": None,
            }
        )

    return rows


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


def _ensure_ingest_columns(frame: pl.DataFrame) -> pl.DataFrame:
    frame = ensure_message_schema(frame)

    columns = frame.columns
    result = frame

    if "anon_author" not in columns:
        result = result.with_columns(pl.col("author").alias("anon_author"))
    else:
        result = result.with_columns(pl.col("anon_author").cast(pl.String))

    if "enriched_summary" not in result.columns:
        result = result.with_columns(pl.lit(None, dtype=pl.String).alias("enriched_summary"))
    else:
        result = result.with_columns(pl.col("enriched_summary").cast(pl.String))

    for column in ("group_slug", "group_name"):
        if column not in result.columns:
            result = result.with_columns(pl.lit(None, dtype=pl.String).alias(column))
        else:
            result = result.with_columns(pl.col(column).cast(pl.String).alias(column))

    if "media_placeholders" not in result.columns:
        result = result.with_columns(
            pl.lit(None, dtype=pl.List(pl.String)).alias("media_placeholders")
        )

    return result


def _extract_group_name_from_chat_file(chat_filename: str) -> str:
    base_name = chat_filename.replace(".txt", "")

    patterns = [
        r"Conversa do WhatsApp com (.+)",
        r"WhatsApp Chat with (.+)",
        r"Chat de WhatsApp con (.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, base_name, re.IGNORECASE)
        if match:
            group_name = match.group(1).strip()
            group_name = re.sub(r"\s*[🀀-🟿]+\s*$", "", group_name).strip()
            return group_name

    return base_name


def _generate_group_slug(group_name: str) -> str:
    slug = unicodedata.normalize("NFKD", group_name)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", slug.lower())
    slug = re.sub(r"[-\s]+", "-", slug)
    slug = slug.strip("-")
    return slug or "whatsapp-group"
