"""WhatsApp source adapter - parses WhatsApp ZIP exports into IR format.

This module consolidates the WhatsApp adapter, parser, and models into a single file.

Performance Notes:
    The parser uses a pure Python approach for optimal performance and safety:
    - ZIP reading: Python zipfile (streaming, no disk extraction)
    - Message parsing: Python regex and stateful iteration (faster than DuckDB/Ibis hybrid due to less serialization)

    Future: When DuckDB zipfs extension is available (DuckDB 1.4.2+), will automatically
    use fully vectorized parsing with `zip://` URIs. Use `egregora doctor` to check
    availability.
"""

from __future__ import annotations

import io
import logging
import math
import re
import unicodedata
import uuid
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, Unpack
from zoneinfo import ZoneInfo

import ibis
import ibis.expr.datatypes as dt
from pydantic import BaseModel

from egregora.data_primitives.document import Document, DocumentType
from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.input_adapters.base import AdapterMeta, InputAdapter
from egregora.ops.media import ATTACHMENT_MARKERS, WA_MEDIA_PATTERN, detect_media_type
from egregora.privacy.anonymizer import anonymize_table
from egregora.privacy.uuid_namespaces import deterministic_author_uuid
from egregora.utils.datetime_utils import parse_datetime_flexible
from egregora.utils.paths import slugify
from egregora.utils.zip import ZipValidationError, ensure_safe_member_size, validate_zip_contents

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)
__all__ = ["WhatsAppAdapter", "discover_chat_file"]


# ============================================================================
# Models
# ============================================================================


class WhatsAppExport(BaseModel):
    """Metadata for a WhatsApp ZIP export."""

    zip_path: Path
    group_name: str
    group_slug: str
    export_date: date
    chat_file: str
    media_files: list[str]


# ============================================================================
# Parser Logic
# ============================================================================

# WhatsApp message line pattern
WHATSAPP_LINE_PATTERN = re.compile(
    r"^(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})(?:,\s*|\s+)(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)\s*[—\-]\s*([^:]+):\s*(.*)$"
)

# Text normalization
_INVISIBLE_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e]")

# WhatsApp mention markers (U+2068 FSI, U+2069 PDI)
# Pattern: @<U+2068>Name<U+2069> where <U+2068> is FIRST STRONG ISOLATE and <U+2069> is POP DIRECTIONAL ISOLATE
WA_MENTION_PATTERN = re.compile(r"@\u2068([^\u2069]+)\u2069")

# Command parsing constants
SET_COMMAND_PARTS = 2
EGREGORA_COMMAND_PATTERN = re.compile("^/egregora\\s+(\\w+)\\s+(.+)$", re.IGNORECASE)

# Regex patterns for command extraction
_COMMAND_ACTION_PATTERN = r"^/egregora\s+([^\s]+)"
_COMMAND_ARGS_PATTERN = r"^/egregora\s+[^\s]+\s*(.*)$"
_FIRST_ARG_PATTERN = r"^([^\s]+)"
_REMAINING_ARGS_PATTERN = r"^[^\s]+\s*(.*)$"

# Time parsing pattern
_AM_PM_PATTERN = re.compile(r"([AaPp][Mm])$")

# Chat file discovery pattern
_CHAT_FILE_PATTERN = re.compile(r"WhatsApp(?: Chat with|.*) (.+)\.txt")


def _normalize_text(value: str) -> str:
    """Normalize unicode text.

    Preserves WhatsApp mention markers (U+2068/U+2069) for proper anonymization,
    while removing other invisible directional marks.
    """
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u202f", " ")
    # Remove invisible marks but keep mention markers (U+2068, U+2069)
    # We'll handle mentions separately in the anonymization pipeline
    return _INVISIBLE_MARKS.sub("", normalized)


# Define parsing strategies in order of preference
def _parse_message_date(token: str) -> date | None:
    """Parse date token into a date object using multiple parsing strategies."""
    normalized = token.strip()
    if not normalized:
        return None

    for dayfirst in (True, False):
        parsed = parse_datetime_flexible(
            normalized,
            default_timezone=UTC,
            parser_kwargs={"dayfirst": dayfirst},
        )
        if parsed:
            return parsed.date()

    return None


def _parse_message_time(time_token: str) -> datetime.time | None:
    """Parse time token into a time object (naive, for later localization)."""
    time_token = time_token.strip()

    am_pm_match = _AM_PM_PATTERN.search(time_token)
    if am_pm_match:
        am_pm = am_pm_match.group(1).upper()
        time_str = time_token[: am_pm_match.start()].strip()
        try:
            return datetime.strptime(f"{time_str} {am_pm}", "%I:%M %p").time()
        except ValueError:
            return None

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

    def start_new_message(self, timestamp: datetime, author_raw: str, initial_text: str) -> None:
        """Finalize pending message and start a new one."""
        self.flush()
        self.message_count += 1
        self._current_entry = {
            "timestamp": timestamp,
            "date": self.current_date,
            "author_raw": author_raw.strip(),
            "_original_lines": [f"{timestamp} - {author_raw}: {initial_text}"],  # Approximate reconstruction
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
        author_uuid = deterministic_author_uuid(self.tenant_id, self.source_identifier, author_raw)

        return {
            "ts": msg["timestamp"],
            "date": msg["date"],
            "message_date": msg["date"].isoformat(),
            "author": author_raw,
            "author_raw": author_raw,
            "author_uuid": str(author_uuid),
            "_author_uuid_hex": author_uuid.hex,  # Temporary internal use
            "text": message_text,
            "original_line": original_text or None,
            "tagged_line": None,
            "_import_order": msg.get("_import_order", 0),  # Temporary internal use
        }

    def get_rows(self) -> list[dict[str, Any]]:
        """Return the list of built message rows."""
        return self._rows


class ZipMessageSource:
    """Iterates over lines from a WhatsApp chat export inside a ZIP file."""

    def __init__(self, export: WhatsAppExport) -> None:
        self.export = export

    def lines(self) -> Iterator[str]:
        """Yield normalized lines from the source file."""
        with zipfile.ZipFile(self.export.zip_path) as zf:
            validate_zip_contents(zf)
            ensure_safe_member_size(zf, self.export.chat_file)
            try:
                with zf.open(self.export.chat_file) as raw:
                    text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                    for line in text_stream:
                        yield _normalize_text(line.rstrip("\n"))
            except UnicodeDecodeError as exc:
                msg = f"Failed to decode chat file '{self.export.chat_file}': {exc}"
                raise ZipValidationError(msg) from exc


def _parse_whatsapp_lines(
    source: ZipMessageSource,
    export: WhatsAppExport,
    timezone: str | ZoneInfo | None,
) -> list[dict[str, Any]]:
    """Pure Python parser for WhatsApp logs.

    Iterates lines once, accumulates multi-line messages, and handles parsing immediately.
    """
    tz = _resolve_timezone(timezone)
    builder = MessageBuilder(
        tenant_id=str(export.group_slug),
        source_identifier="whatsapp",
        current_date=export.export_date,
        timezone=tz,
    )

    for line in source.lines():
        match = WHATSAPP_LINE_PATTERN.match(line)

        if match:
            date_str, time_str, author_raw, message_part = match.groups()

            # Update builder date context if valid
            msg_date = _parse_message_date(date_str)
            if msg_date:
                builder.current_date = msg_date

            msg_time = _parse_message_time(time_str)

            # Skip invalid times but keep date update
            if not msg_time:
                builder.flush()
                continue

            timestamp = datetime.combine(builder.current_date, msg_time, tzinfo=tz).astimezone(UTC)
            builder.start_new_message(timestamp, author_raw, message_part)

        else:
            # Handle continuation
            builder.append_line(line, line)  # For continuation, line IS the text part

    builder.flush()
    return builder.get_rows()


def _add_message_ids(messages: Table) -> Table:
    """Add deterministic message_id column based on milliseconds since group creation."""
    if int(messages.count().execute()) == 0:
        return messages

    min_ts = messages.ts.min()
    delta_ms = ((messages.ts.epoch_seconds() - min_ts.epoch_seconds()) * 1000).round().cast("int64")

    # Order by timestamp and import order (if present) to ensure determinism
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


# ============================================================================
# Command Parsing
# ============================================================================


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


def extract_commands(messages: Table) -> list[dict]:
    """Extract egregora commands from parsed Table."""
    normalized = messages.mutate(normalized_message=normalize_smart_quotes(messages.text))
    filtered = normalized.filter(normalized.normalized_message.lower().startswith("/egregora"))
    trimmed = filtered.mutate(trimmed_message=filtered.normalized_message.strip())

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


def parse_source(
    export: WhatsAppExport,
    timezone: str | ZoneInfo | None = None,
    *,
    expose_raw_author: bool = False,
    source_identifier: str = "whatsapp",
) -> Table:
    """Parse WhatsApp export using pure Ibis/DuckDB operations."""
    source = ZipMessageSource(export)
    rows = _parse_whatsapp_lines(source, export, timezone)

    if not rows:
        logger.warning("No messages found in %s", export.zip_path)
        return ibis.memtable([], schema=IR_MESSAGE_SCHEMA)

    messages = ibis.memtable(rows)
    if "_import_order" in messages.columns:
        messages = messages.order_by([messages.ts, messages["_import_order"]])
    else:
        messages = messages.order_by("ts")

    messages = _add_message_ids(messages)

    if "_import_order" in messages.columns:
        messages = messages.drop("_import_order")

    if not expose_raw_author:
        messages = anonymize_table(messages)

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

    ir_messages = messages.mutate(
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

    return ir_messages.select(*IR_MESSAGE_SCHEMA.names)


# ============================================================================
# Adapter Implementation
# ============================================================================


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in zip_path and infer the group name."""
    with zipfile.ZipFile(zip_path) as zf:
        candidates: list[tuple[int, str, str]] = []
        for member in zf.namelist():
            if not member.endswith(".txt") or member.startswith("__"):
                continue

            match = _CHAT_FILE_PATTERN.match(Path(member).name)
            file_info = zf.getinfo(member)
            score = file_info.file_size
            if match:
                score += 1_000_000
                group_name = match.group(1)
            else:
                group_name = Path(member).stem
            candidates.append((score, group_name, member))

        if not candidates:
            msg = f"No WhatsApp chat file found in {zip_path}"
            raise ValueError(msg)

        candidates.sort(reverse=True, key=lambda item: item[0])
        _, group_name, member = candidates[0]
        return (group_name, member)


class _EmptyKwargs(TypedDict):
    """Empty TypedDict for unused kwargs in adapter methods."""


class DeliverMediaKwargs(TypedDict, total=False):
    """Kwargs for WhatsAppAdapter.deliver_media method."""

    zip_path: Path


def _convert_whatsapp_media_to_markdown(message: str) -> str:
    """Convert WhatsApp media references to markdown format."""
    if not message:
        return message
    result = message
    media_files = WA_MEDIA_PATTERN.findall(message)
    for filename in media_files:
        media_type = detect_media_type(Path(filename)) or "file"
        if media_type == "image":
            markdown = f"![Image]({filename})"
        elif media_type == "video":
            markdown = f"[Video]({filename})"
        elif media_type == "audio":
            markdown = f"[Audio]({filename})"
        elif media_type == "document":
            markdown = f"[Document]({filename})"
        else:
            markdown = f"[File]({filename})"
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(filename) + "\\s*" + re.escape(marker)
            result = re.sub(pattern, markdown, result, flags=re.IGNORECASE)
        if filename in result and markdown not in result:
            result = re.sub("\\b" + re.escape(filename) + "\\b", markdown, result)
    return result


def _convert_whatsapp_mentions_to_markdown(message: str, tenant_id: str, source: str) -> str:
    """Convert WhatsApp unicode-wrapped mentions to profile wikilinks.

    Converts WhatsApp's unicode-wrapped mention format to profile links.
    Example: @NAME (wrapped with U+2068/U+2069) becomes [[profile/uuid]]
    where uuid is deterministically generated from the mentioned name.

    Args:
        message: Message text containing mentions
        tenant_id: Tenant identifier for UUID generation
        source: Source adapter name (e.g., 'whatsapp')

    Returns:
        Message with mentions converted to [[profile/uuid]] wikilinks

    """
    if not message:
        return message

    def replace_mention(match):
        """Replace a single mention with its profile link."""
        mentioned_name = match.group(1)
        # Generate deterministic UUID for this author
        author_uuid = deterministic_author_uuid(tenant_id, source, mentioned_name)
        # Return wikilink format: [[profile/uuid]]
        return f"[[profile/{author_uuid}]]"

    # Replace unicode-wrapped mentions with profile links
    result = WA_MENTION_PATTERN.sub(replace_mention, message)
    return result


def build_message_attrs(
    original_line: ibis.Expr,
    tagged_line: ibis.Expr,
    message_date: ibis.Expr,
) -> ibis.Expr:
    """Return message metadata serialized as JSON when any field is present."""
    attrs_struct = ibis.struct(
        {
            "original_line": original_line,
            "tagged_line": tagged_line,
            "message_date": message_date,
        }
    )
    has_metadata = ibis.coalesce(original_line, tagged_line, message_date).notnull()
    attrs_json = attrs_struct.cast(dt.json).cast(dt.string)
    empty_json = ibis.literal(None, type=dt.string)
    return ibis.cases(
        (has_metadata, attrs_json),
        else_=empty_json,
    )


class WhatsAppAdapter(InputAdapter):
    """Source adapter for WhatsApp ZIP exports."""

    def __init__(self, *, author_namespace: uuid.UUID | None = None) -> None:
        self._author_namespace = author_namespace

    @property
    def source_name(self) -> str:
        return "WhatsApp"

    @property
    def source_identifier(self) -> str:
        return "whatsapp"

    @property
    def content_summary(self) -> str:
        return (
            "This dataset contains anonymized WhatsApp group conversations exported "
            "directly from the mobile chat history."
        )

    def get_adapter_metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="WhatsApp",
            version="1.0.0",
            source="whatsapp",
            doc_url="https://github.com/franklinbaldo/egregora#whatsapp-exports",
            ir_version="v1",
        )

    def parse(self, input_path: Path, *, timezone: str | None = None, **_kwargs: _EmptyKwargs) -> Table:
        if not input_path.exists():
            msg = f"Input path does not exist: {input_path}"
            raise FileNotFoundError(msg)
        if not input_path.is_file() or not str(input_path).endswith(".zip"):
            msg = f"Expected a ZIP file, got: {input_path}"
            raise ValueError(msg)
        group_name, chat_file = discover_chat_file(input_path)
        export = WhatsAppExport(
            zip_path=input_path,
            group_name=group_name,
            group_slug=group_name.lower().replace(" ", "-"),
            export_date=datetime.now(tz=UTC).date(),
            chat_file=chat_file,
            media_files=[],
        )
        messages_table = parse_source(
            export,
            timezone=timezone,
            expose_raw_author=True,
        )

        @ibis.udf.scalar.python
        def convert_media_to_markdown(message: str | None) -> str | None:
            if message is None:
                return None
            # Convert media references
            result = _convert_whatsapp_media_to_markdown(message)
            # Convert mentions to profile links
            result = _convert_whatsapp_mentions_to_markdown(result, export.group_slug, "whatsapp")
            return result

        # IR v1: use 'text' column instead of 'message'
        messages_table = messages_table.mutate(text=convert_media_to_markdown(messages_table.text))

        logger.debug("Parsed WhatsApp export with %s messages", messages_table.count().execute())
        return messages_table

    def deliver_media(self, media_reference: str, **kwargs: Unpack[DeliverMediaKwargs]) -> Document | None:
        """Deliver media file from WhatsApp ZIP as a Document."""
        if not self._validate_media_reference(media_reference):
            return None
        zip_path = self._get_validated_zip_path(kwargs)
        if not zip_path:
            return None

        return self._extract_media_from_zip(zip_path, media_reference)

    def _validate_media_reference(self, media_reference: str) -> bool:
        if ".." in media_reference or "/" in media_reference or "\\" in media_reference:
            logger.warning("Suspicious media reference (path traversal attempt): %s", media_reference)
            return False
        return True

    def _get_validated_zip_path(self, kwargs: DeliverMediaKwargs) -> Path | None:
        zip_path = kwargs.get("zip_path")
        if not zip_path:
            logger.warning("deliver_media() called without zip_path kwarg")
            return None
        if not isinstance(zip_path, Path):
            zip_path = Path(zip_path)
        if not zip_path.exists():
            logger.warning("ZIP file does not exist: %s", zip_path)
            return None
        return zip_path

    def _extract_media_from_zip(self, zip_path: Path, media_reference: str) -> Document | None:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                found_path = self._find_media_in_zip(zf, media_reference)
                if not found_path:
                    logger.debug("Media file not found in ZIP: %s", media_reference)
                    return None

                file_content = zf.read(found_path)
                logger.debug("Delivered media: %s", media_reference)

                # Determine media type from extension to set metadata
                from egregora.ops.media import detect_media_type

                media_type = detect_media_type(Path(media_reference))
                media_slug = slugify(Path(media_reference).stem) if media_reference else None

                return Document(
                    content=file_content,
                    type=DocumentType.MEDIA,
                    metadata={
                        "original_filename": media_reference,
                        "media_type": media_type,
                        "slug": media_slug or None,
                        "nav_exclude": True,
                        "hide": ["navigation"],
                    },
                )
        except zipfile.BadZipFile:
            logger.exception("Invalid ZIP file: %s", zip_path)
            return None
        except (KeyError, OSError, PermissionError):
            logger.exception("Failed to extract %s from %s", media_reference, zip_path)
            return None

    def _find_media_in_zip(self, zf: zipfile.ZipFile, media_reference: str) -> str | None:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if Path(info.filename).name.lower() == media_reference.lower():
                return info.filename
        return None

    def get_metadata(self, input_path: Path, **_kwargs: _EmptyKwargs) -> dict[str, Any]:
        if not input_path.exists():
            msg = f"Input path does not exist: {input_path}"
            raise FileNotFoundError(msg)
        group_name, chat_file = discover_chat_file(input_path)
        group_slug = group_name.lower().replace(" ", "-")
        return {
            "group_name": group_name,
            "group_slug": group_slug,
            "chat_file": chat_file,
            "export_date": datetime.now(tz=UTC).date().isoformat(),
        }
