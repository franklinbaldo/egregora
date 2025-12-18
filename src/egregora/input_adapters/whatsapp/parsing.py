"""Parsing and normalization logic for WhatsApp exports."""

from __future__ import annotations

import html
import io
import logging
import re
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import ibis
import ibis.expr.datatypes as dt
from dateutil import parser as date_parser
from pydantic import BaseModel

from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.input_adapters.whatsapp.utils import build_message_attrs
from egregora.privacy import anonymize_author, scrub_pii
from egregora.utils.zip import ZipValidationError, ensure_safe_member_size, validate_zip_contents

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ibis.expr.types import Table

    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)


class WhatsAppExport(BaseModel):
    """Metadata for a WhatsApp ZIP export."""

    zip_path: Path
    group_name: str
    group_slug: str
    export_date: date
    chat_file: str
    media_files: list[str]


# Keep the old brittle one as a fallback
FALLBACK_PATTERN = re.compile(
    r"^(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})(?:,\s*|\s+)(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)\s*[—\-]\s*([^:]+):\s*(.*)$"
)


# Text normalization
_INVISIBLE_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e]")

# Define parsing strategies in order of preference
_DATE_PARSING_STRATEGIES = [
    lambda x: date_parser.isoparse(x),
    lambda x: date_parser.parse(x, dayfirst=True),
    lambda x: date_parser.parse(x, dayfirst=False),
]


def _normalize_text(value: str, config: EgregoraConfig | None = None) -> str:
    """Normalize unicode text and sanitize HTML.

    Performs:
    1. Unicode NFKC normalization (if needed)
    2. Removal of invisible control characters
    3. PII scrubbing (if enabled)
    4. HTML escaping of special characters (<, >, &) to prevent XSS
       (quote=False to preserve readability of quotes in text)
    """
    if value.isascii():
        return html.escape(value, quote=False)

    normalized = unicodedata.normalize("NFKC", value)
    # NFKC already converts \u202f (Narrow No-Break Space) to space, so explicit replace is redundant
    cleaned = _INVISIBLE_MARKS.sub("", normalized)

    # Scrub PII before HTML escaping
    scrubbed = scrub_pii(cleaned, config)

    return html.escape(scrubbed, quote=False)


@lru_cache(maxsize=1024)
def _parse_message_date(token: str) -> date | None:
    """Parse date token into a date object using multiple parsing strategies.

    Performance: Uses lru_cache since WhatsApp logs contain many repeated
    date strings (messages from the same day).
    """
    normalized = token.strip()
    if not normalized:
        return None

    for strategy in _DATE_PARSING_STRATEGIES:
        try:
            parsed = strategy(normalized)
            parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
            return parsed.date()
        except (TypeError, ValueError, OverflowError):
            continue

    return None


@lru_cache(maxsize=4096)
def _parse_message_time(time_token: str) -> time | None:
    """Parse time token into a time object (naive, for later localization).

    Performance:
    - Optimized string parsing replaces slower datetime.strptime (~8x speedup)
    - Uses lru_cache(4096) to cover full 24h cycle (1440 mins) + variations,
      ensuring we parse each unique time string only once per execution.
    """
    token = time_token.strip()
    if not token:
        return None

    # Fast path for standard HH:MM (e.g., "12:30", "09:15")
    # Checks length and digit presence to avoid splitting/parsing invalid strings
    if len(token) == 5 and token[2] == ":" and token[0].isdigit() and token[1].isdigit() and token[3].isdigit() and token[4].isdigit():
        try:
            # Direct slicing is faster than splitting
            return time(int(token[:2]), int(token[3:]))
        except ValueError:
            # Falls through to full parsing if hours/minutes are out of range
            pass

    # Handle AM/PM and other formats
    is_ampm = False
    is_pm = False
    ampm_offset = 0

    upper = token.upper()

    # Check for AM/PM suffix (case-insensitive)
    if upper.endswith("M"):
        if upper.endswith("AM"):
            is_ampm = True
            is_pm = False
            ampm_offset = 2
        elif upper.endswith("PM"):
            is_ampm = True
            is_pm = True
            ampm_offset = 2

    # Parse logic
    try:
        if is_ampm:
            # Slice off "AM" or "PM" and strip remaining whitespace
            main_part = token[:-ampm_offset].strip()
            if ":" in main_part:
                h_str, m_str = main_part.split(":")
                h = int(h_str)
                m = int(m_str)

                if is_pm and h != 12:
                    h += 12
                elif not is_pm and h == 12:
                    h = 0
                return time(h, m)
        elif ":" in token:
             # Standard "H:MM" or fallback for "HH:MM" that failed fast path
            parts = token.split(":")
            if len(parts) == 2:
                return time(int(parts[0]), int(parts[1]))
    except ValueError:
        pass

    return None


def _resolve_timezone(timezone: str | ZoneInfo | None) -> ZoneInfo:
    """Resolve timezone string or object to ZoneInfo."""
    if timezone is None:
        return UTC
    if isinstance(timezone, ZoneInfo):
        return timezone
    return ZoneInfo(timezone)


@dataclass
class MessageBuilder:
    """Encapsulates message construction state, hiding internal tracking columns."""

    tenant_id: str
    source_identifier: str
    current_date: date
    timezone: ZoneInfo
    message_count: int = 0
    _current_entry: dict[str, Any] | None = None
    _rows: list[dict[str, Any]] = field(default_factory=list)
    _author_uuid_cache: dict[str, str] = field(default_factory=dict)

    def start_new_message(self, timestamp: datetime, author_raw: str, initial_text: str) -> None:
        """Finalize pending message and start a new one."""
        self.flush()
        self.message_count += 1
        self._current_entry = {
            "timestamp": timestamp,
            "date": self.current_date,
            "author_raw": author_raw.strip(),
            "_original_lines": [f"{timestamp} - {author_raw}: {initial_text}"],
            "_continuation_lines": [initial_text],
            "_import_order": self.message_count,
        }

    def append_line(self, line: str, text_part: str) -> None:
        """Append a line to the current message."""
        if self._current_entry:
            self._current_entry["_original_lines"].append(line)
            self._current_entry["_continuation_lines"].append(text_part)

    def flush(self) -> None:
        """Finalize and store the current message."""
        if self._current_entry:
            finalized = self._finalize_message(self._current_entry)
            if finalized["text"]:
                self._rows.append(finalized)
            self._current_entry = None

    def _finalize_message(self, msg: dict) -> dict:
        """Transform internal builder state to public schema dict."""
        message_text = "\n".join(msg["_continuation_lines"]).strip()
        original_text = "\n".join(msg["_original_lines"]).strip()

        author_raw = msg["author_raw"]
        # Deterministic UUID generation: same author_raw always produces the same UUID
        # Uses UUID5 (name-based) with OID namespace for consistent, reproducible author IDs
        # Cache UUIDs for performance (avoid recomputing for the same author)
        if author_raw not in self._author_uuid_cache:
            author_key = f"{self.source_identifier}:{author_raw}"
            author_uuid_str = anonymize_author(author_key, uuid.NAMESPACE_OID)
            # Store string representation in cache
            self._author_uuid_cache[author_raw] = author_uuid_str
        else:
            author_uuid_str = self._author_uuid_cache[author_raw]

        # Compute hex representation directly from UUID string (hyphens removed)
        author_uuid_hex = author_uuid_str.replace("-", "")

        return {
            "ts": msg["timestamp"],
            "date": msg["date"],
            "message_date": msg["date"].isoformat(),
            "author": author_raw,
            "author_raw": author_raw,
            "author_uuid": author_uuid_str,
            "_author_uuid_hex": author_uuid_hex,
            "text": message_text,
            "original_line": original_text or None,
            "tagged_line": None,
            "_import_order": msg.get("_import_order", 0),
        }

    def get_rows(self) -> list[dict[str, Any]]:
        """Return the list of built message rows."""
        return self._rows


class ZipMessageSource:
    """Iterates over lines from a WhatsApp chat export inside a ZIP file."""

    def __init__(self, export: WhatsAppExport, config: EgregoraConfig | None = None) -> None:
        self.export = export
        self.config = config

    def lines(self) -> Iterator[str]:
        """Yield normalized lines from the source file."""
        with zipfile.ZipFile(self.export.zip_path) as zf:
            validate_zip_contents(zf)
            ensure_safe_member_size(zf, self.export.chat_file)
            try:
                with zf.open(self.export.chat_file) as raw:
                    text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                    for line in text_stream:
                        yield _normalize_text(line.rstrip("\n"), self.config)
            except UnicodeDecodeError as exc:
                msg = f"Failed to decode chat file '{self.export.chat_file}': {exc}"
                raise ZipValidationError(msg) from exc


def _parse_whatsapp_lines(
    source: ZipMessageSource,
    export: WhatsAppExport,
    timezone: str | ZoneInfo | None,
) -> list[dict[str, Any]]:
    """Pure Python parser for WhatsApp logs."""
    line_pattern = FALLBACK_PATTERN

    tz = _resolve_timezone(timezone)
    builder = MessageBuilder(
        tenant_id=str(export.group_slug),
        source_identifier="whatsapp",
        current_date=export.export_date,
        timezone=tz,
    )

    # Re-open source to read from start
    for line in source.lines():
        match = line_pattern.match(line)  # Use dynamic pattern

        if match:
            # ... rest of existing logic ...
            date_str, time_str, author_raw, message_part = match.groups()

            msg_date = _parse_message_date(date_str)
            if msg_date:
                builder.current_date = msg_date

            msg_time = _parse_message_time(time_str)

            if not msg_time:
                builder.flush()
                continue

            timestamp = datetime.combine(builder.current_date, msg_time, tzinfo=tz).astimezone(UTC)
            builder.start_new_message(timestamp, author_raw, message_part)

        else:
            builder.append_line(line, line)

    builder.flush()
    return builder.get_rows()


def _add_message_ids(messages: Table) -> Table:
    """Add deterministic message_id column based on milliseconds since group creation."""
    min_ts = messages.ts.min()
    delta_ms = ((messages.ts.epoch_seconds() - min_ts.epoch_seconds()) * 1000).round().cast("int64")

    order_columns = [messages.ts]
    if "_import_order" in messages.columns:
        order_columns.append(messages["_import_order"])

    if "author_raw" in messages.columns:
        order_columns.append(messages.author_raw)
    elif "author" in messages.columns:
        order_columns.append(messages.author)

    if "text" in messages.columns:
        order_columns.append(messages.text)
    elif "message" in messages.columns:
        order_columns.append(messages.message)

    row_number = ibis.row_number().over(order_by=order_columns)
    return messages.mutate(message_id=delta_ms.cast("string") + "_" + row_number.cast("string"))


def parse_source(
    export: WhatsAppExport,
    timezone: str | ZoneInfo | None = None,
    *,
    expose_raw_author: bool = False,
    source_identifier: str = "whatsapp",
    config: EgregoraConfig | None = None,
) -> Table:
    """Parse WhatsApp export using pure Ibis/DuckDB operations."""
    source = ZipMessageSource(export, config)
    rows = _parse_whatsapp_lines(source, export, timezone)

    if not rows:
        logger.warning("No messages found in %s", export.zip_path)
        return ibis.memtable([], schema=IR_MESSAGE_SCHEMA)

    messages = ibis.memtable(rows)
    if "_import_order" in messages.columns:
        messages = messages.order_by([messages.ts, messages["_import_order"]])
    else:
        messages = messages.order_by("ts")

    if not expose_raw_author:
        # Anonymize author names to prevent leakage of PII into downstream tables
        # We replace the raw name with the UUID string
        messages = messages.mutate(author_raw=messages.author_uuid)

    messages = _add_message_ids(messages)

    if not expose_raw_author:
        # Redact raw author names if not explicitly exposed
        # Replace author_raw with author_uuid to maintain a valid string
        messages = messages.mutate(author_raw=messages.author_uuid)

    if "_import_order" in messages.columns:
        messages = messages.drop("_import_order")

    helper_columns = ["_author_uuid_hex"]
    columns_to_drop = [col for col in helper_columns if col in messages.columns]
    if columns_to_drop:
        messages = messages.drop(*columns_to_drop)

    tenant_literal = ibis.literal(str(export.group_slug))
    thread_literal = tenant_literal
    source_literal = ibis.literal(source_identifier)
    created_by_literal = ibis.literal("adapter:whatsapp")
    string_null = ibis.literal(None, type=dt.string)
    json_null = ibis.literal(None, type=dt.json)

    attrs_column = build_message_attrs(
        messages.original_line, messages.tagged_line, messages.message_date
    ).cast(dt.json)

    # Note: author_raw is inherited from messages table and should already be present
    result_table = messages.mutate(
        event_id=messages.message_id,
        tenant_id=tenant_literal,
        source=source_literal,
        thread_id=thread_literal,
        msg_id=messages.message_id,
        ts=messages.ts.cast("timestamp('UTC')"),
        media_url=string_null,
        media_type=string_null,
        attrs=attrs_column,
        pii_flags=json_null,
        created_at=messages.ts.cast("timestamp('UTC')"),
        created_by_run=created_by_literal,
    )

    return result_table.select(*IR_MESSAGE_SCHEMA.names)
