"""WhatsApp source adapter - parses WhatsApp ZIP exports into IR format.

This module consolidates the WhatsApp adapter, parser, and models into a single file.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
import uuid
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, Unpack
from zoneinfo import ZoneInfo

import ibis
from dateutil import parser as date_parser
from pydantic import BaseModel

from egregora.data_primitives import GroupSlug
from egregora.data_primitives.document import Document, DocumentType
from egregora.input_adapters.base import AdapterMeta, InputAdapter
from egregora.privacy.anonymizer import anonymize_table
from egregora.privacy.uuid_namespaces import deterministic_author_uuid

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
    group_slug: GroupSlug
    export_date: date
    chat_file: str
    media_files: list[str]


# ============================================================================
# Parser Logic
# ============================================================================

# Internal columns for tracking during parsing
_IMPORT_ORDER_COLUMN = "_import_order"
_IMPORT_SOURCE_COLUMN = "_import_source"
DEFAULT_CHAT_FILE_LIMIT_BYTES = 2 * 1024**3
_WHATSAPP_OUTPUT_SCHEMA = ibis.schema(
    {
        "ts": "timestamp",
        "date": "date",
        "author": "string",
        "author_raw": "string",
        "author_uuid": "string",
        "text": "string",
        "original_line": "string",
        "tagged_line": "string",
        "message_id": "string",
    }
)

# WhatsApp message line pattern
WHATSAPP_LINE_PATTERN = re.compile(
    r"^(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})(?:,\s*|\s+)(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)\s*[—\-]\s*([^:]+):\s*(.*)$"
)

# Text normalization
_INVISIBLE_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e]")

# Command parsing constants
SET_COMMAND_PARTS = 2
EGREGORA_COMMAND_PATTERN = re.compile("^/egregora\\s+(\\w+)\\s+(.+)$", re.IGNORECASE)


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

    try:
        parsed = date_parser.isoparse(normalized)
        parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        return parsed.date()
    except (TypeError, ValueError, OverflowError):
        pass

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

    am_pm_match = re.search(r"([AaPp][Mm])$", time_token)
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


def _finalize_message(msg: dict, tenant_id: str, source: str) -> dict:
    """Finalize a message by joining continuation lines - returns IR schema format."""
    message_text = "\n".join(msg["_continuation_lines"]).strip()
    original_text = "\n".join(msg["_original_lines"]).strip()

    author_raw = msg["author_raw"]
    author_uuid = deterministic_author_uuid(tenant_id, source, author_raw)

    return {
        "ts": msg["timestamp"],
        "date": msg["date"],
        "author": author_raw,
        "author_raw": author_raw,
        "author_uuid": str(author_uuid),
        "text": message_text,
        "original_line": original_text or None,
        "tagged_line": None,
    }


def _parse_messages_duckdb(
    lines: list[str], export: WhatsAppExport, timezone: str | ZoneInfo | None
) -> list[dict]:
    """Parse messages using Ibis/DuckDB vectorized operations.

    This implementation leverages DuckDB's vectorized string functions for high performance.
    It creates an in-memory table from the lines, applies regex extraction,
    and uses window functions to group multi-line messages.
    """
    if not lines:
        return []

    # Normalize text (NFKC) in Python first as it's robust
    # TODO: Investigate if DuckDB has built-in unicode normalization
    normalized_lines = [_normalize_text(line) for line in lines]

    # Create an Ibis table from lines
    raw_table = ibis.memtable({"line": normalized_lines, "line_id": range(len(normalized_lines))})

    # Regex patterns adapted for DuckDB's regexp_extract
    # Pattern: (date), (time) - (author): (message)
    # Note: DuckDB regex syntax is POSIX extended or RE2
    # We need to capture groups 1, 2, 3, 4
    regex_pattern = r"^(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})(?:,\s*|\s+)(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)\s*[—\-]\s*([^:]+):\s*(.*)$"

    parsed = raw_table.mutate(
        is_header=raw_table.line.re_search(regex_pattern),
        date_str=raw_table.line.re_extract(regex_pattern, 1),
        time_str=raw_table.line.re_extract(regex_pattern, 2),
        author_raw=raw_table.line.re_extract(regex_pattern, 3),
        message_part=raw_table.line.re_extract(regex_pattern, 4),
    )

    # Identify message groups
    # A new group starts where is_header is True
    # We use cumulative sum (scan) to assign group IDs
    grouped = parsed.mutate(msg_group_id=parsed.is_header.cast("int").cumsum())

    # Filter out lines before the first valid message
    valid_messages = grouped.filter(grouped.msg_group_id > 0)

    # Aggregate messages within groups
    # For header lines, we use extracted parts.
    # For continuation lines, we use the full line.
    # The first line of a group is the header.
    aggregated = valid_messages.group_by("msg_group_id").aggregate(
        # Take header info from the first line of the group
        date_str=valid_messages.date_str.first(),
        time_str=valid_messages.time_str.first(),
        author_raw=valid_messages.author_raw.first(),
        # Combine text: header's message_part + subsequent full lines
        # We can't easily use string_agg with complex condition in one go in standard Ibis without window functions
        # But since we grouped, we can try list_agg or similar if supported, or do a window operation before aggregate.
        # Strategy:
        # 1. Identify content for each line:
        #    - Header line: message_part
        #    - Continuation line: line
        # 2. String agg them ordered by line_id
    )

    # Let's refine the aggregation strategy using window functions before group_by if possible,
    # or just collect and process. DuckDB's string_agg preserves order if order_by is used.

    # Helper expression for content content
    content_expr = ibis.cases(
        (valid_messages.is_header, valid_messages.message_part),
        else_=valid_messages.line,
    )

    final_table = (
        valid_messages.group_by("msg_group_id")
        .aggregate(
            date_str=valid_messages.date_str.first(),
            time_str=valid_messages.time_str.first(),
            author_raw=valid_messages.author_raw.first(),
            # Use standard aggregation if group_concat isn't available on older ibis versions
            # DuckDB supports list_agg or string_agg
            # Ibis usually exposes group_concat, but let's try a more backend-agnostic approach or direct SQL if needed.
            # Since we are using ibis.memtable (DuckDB backend), we can use .agg(ibis.literal("\n").join(content_expr))? No.
            # Let's try ibis.string_agg if group_concat fails. But Ibis standardizes.
            # The error says 'ibis' module has no attribute 'group_concat'. It might be an expression method.
            # Try content_expr.group_concat("\n")
            full_text=content_expr.group_concat(sep="\n"),
        )
        .order_by("msg_group_id")
    )

    # Execute to get Python objects for final date parsing (since date formats vary wildly)
    # We could do date parsing in SQL if formats were standard, but WhatsApp dates are messy.
    result_df = final_table.execute()

    rows: list[dict] = []
    tz = _resolve_timezone(timezone)
    tenant_id = str(export.group_slug)
    source_identifier = "whatsapp"
    current_date = export.export_date

    # Iterate and finalize using Python for date logic and UUID generation
    # This is much faster than iterating raw lines because rows are already aggregated (10x-100x reduction)
    for row in result_df.to_dict(orient="records"):
        text = row["full_text"]
        if not text or not text.strip():
            continue

        # Date parsing (reuse helper)
        msg_date = _parse_message_date(row["date_str"])
        if msg_date:
            current_date = msg_date
        else:
            msg_date = current_date

        # Time parsing
        msg_time = _parse_message_time(row["time_str"])
        if msg_time is None:
            continue

        timestamp = datetime.combine(msg_date, msg_time, tzinfo=tz)
        author_raw = row["author_raw"].strip()

        # Use existing finalizer logic
        msg_dict = {
            "timestamp": timestamp,
            "date": msg_date,
            "author_raw": author_raw,
            "_continuation_lines": [
                text
            ],  # Already joined, but finalize expects list structure or we adapt finalize
            "_original_lines": [],  # We skip original lines tracking for speed in this path
        }

        # Adapted finalizer for pre-joined text
        author_uuid = deterministic_author_uuid(tenant_id, source_identifier, author_raw)

        finalized = {
            "ts": timestamp,
            "date": msg_date,
            "author": author_raw,
            "author_raw": author_raw,
            "author_uuid": str(author_uuid),
            "text": text.strip(),
            "original_line": None,
            "tagged_line": None,
            _IMPORT_ORDER_COLUMN: row["msg_group_id"],
        }
        rows.append(finalized)

    return rows


def _add_message_ids(messages: Table) -> Table:
    """Add deterministic message_id column based on milliseconds since group creation."""
    if int(messages.count().execute()) == 0:
        return messages

    min_ts = messages.ts.min()
    delta_ms = ((messages.ts.epoch_seconds() - min_ts.epoch_seconds()) * 1000).round().cast("int64")

    order_columns = [messages.ts]
    if _IMPORT_SOURCE_COLUMN in messages.columns:
        order_columns.append(messages[_IMPORT_SOURCE_COLUMN])
    if _IMPORT_ORDER_COLUMN in messages.columns:
        order_columns.append(messages[_IMPORT_ORDER_COLUMN])

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
        action=trimmed.trimmed_message.re_extract(r"^/egregora\s+([^\s]+)", 1).lower(),
        args_raw=trimmed.trimmed_message.re_extract(r"^/egregora\s+[^\s]+\s*(.*)$", 1),
    )

    enriched = parsed.mutate(
        args_trimmed=ibis.coalesce(parsed.args_raw, ibis.literal("")).strip(),
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
        if target is not None and target == target:
            command_payload["target"] = target

        value = row.get("command_value")
        if value is not None and value == value:
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
) -> Table:
    """Parse WhatsApp export using pure Ibis/DuckDB operations."""
    try:
        backend = ibis.get_backend()
        _install_zipfs_extension(backend)

        chat_uri = _build_zip_uri(export.zip_path, export.chat_file)
        lines_table = ibis.read_csv(
            chat_uri,
            columns={"line": "string"},
            header=False,
            delim="\t",
            auto_detect=False,
        )

        lines = [value or "" for value in lines_table["line"].execute().tolist()]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "zipfs path read failed for %s: %s; falling back to in-memory extraction",
            export.zip_path,
            exc,
        )
        lines = _read_chat_lines_with_zipfile(export.zip_path, export.chat_file)

    if not lines:
        logger.warning("No messages found in %s", export.zip_path)
        return ibis.memtable([], schema=_WHATSAPP_OUTPUT_SCHEMA)

    rows = _parse_messages_duckdb(lines, export, timezone)

    if not rows:
        return ibis.memtable([], schema=_WHATSAPP_OUTPUT_SCHEMA)

    messages = ibis.memtable(rows)
    if _IMPORT_ORDER_COLUMN in messages.columns:
        messages = messages.order_by([messages.ts, messages[_IMPORT_ORDER_COLUMN]])
    else:
        messages = messages.order_by("ts")

    messages = _add_message_ids(messages)

    if _IMPORT_ORDER_COLUMN in messages.columns:
        messages = messages.drop(_IMPORT_ORDER_COLUMN)

    if not expose_raw_author:
        messages = anonymize_table(messages)

    extra_columns = [column for column in messages.columns if column not in _WHATSAPP_OUTPUT_SCHEMA.names]
    if extra_columns:
        messages = messages.drop(*extra_columns)
    selected_columns = [
        messages[column] for column in _WHATSAPP_OUTPUT_SCHEMA.names if column in messages.columns
    ]
    messages = messages.select(*selected_columns)

    return messages


def _build_zip_uri(zip_path: Path, member_name: str) -> str:
    return f"zip://{zip_path.as_posix()}!{member_name}"


def _install_zipfs_extension(backend: ibis.BaseBackend) -> None:
    try:
        backend.raw_sql("LOAD zipfs")
        return
    except Exception:
        logger.debug("zipfs extension not preloaded; attempting install")

    try:
        backend.raw_sql("SET custom_extension_repository='https://extensions.duckdb.org'")
    except Exception:
        logger.debug("Unable to set custom_extension_repository for DuckDB")

    try:
        backend.raw_sql("INSTALL zipfs")
        backend.raw_sql("LOAD zipfs")
    except Exception as exc:
        msg = (
            "DuckDB zipfs extension is required to read WhatsApp exports. "
            "Run `egregora doctor` to verify extension availability."
        )
        raise RuntimeError(msg) from exc


def _validate_zip_safety(
    zip_path: Path, target_file: str, *, max_bytes: int = DEFAULT_CHAT_FILE_LIMIT_BYTES
) -> None:
    """Lightweight 'Bouncer' to prevent processing zip bombs."""
    with zipfile.ZipFile(zip_path) as zf:
        try:
            info = zf.getinfo(target_file)
        except KeyError:
            return

        if info.file_size > max_bytes:
            raise ValueError(
                f"Security limit exceeded: '{target_file}' is {info.file_size} bytes "
                f"(max allowed: {max_bytes}). Processing aborted."
            )


def _read_chat_lines_with_zipfile(zip_path: Path, chat_file: str) -> list[str]:
    with zipfile.ZipFile(zip_path) as zf:
        try:
            with zf.open(chat_file) as raw:
                text_stream = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
                return [line.rstrip("\n") for line in text_stream]
        except UnicodeDecodeError as exc:
            msg = f"Failed to decode chat file '{chat_file}': {exc}"
            raise ValueError(msg) from exc


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

            pattern = r"WhatsApp(?: Chat with|.*) (.+)\\.txt"
            match = re.match(pattern, Path(member).name)
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


ATTACHMENT_MARKERS = ("(arquivo anexado)", "(file attached)", "(archivo adjunto)", "\u200e<attached:")
WA_MEDIA_PATTERN = re.compile("\\b((?:IMG|VID|AUD|PTT|DOC)-\\d+-WA\\d+\\.\\w+)\\b")
MEDIA_EXTENSIONS = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    ".mp4": "video",
    ".mov": "video",
    ".3gp": "video",
    ".avi": "video",
    ".opus": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
}


def _detect_media_type(filename: str) -> str:
    """Detect media type from filename for markdown alt text."""
    ext = Path(filename).suffix.lower()
    return MEDIA_EXTENSIONS.get(ext, "file")


def _convert_whatsapp_media_to_markdown(message: str) -> str:
    """Convert WhatsApp media references to markdown format."""
    if not message:
        return message
    result = message
    media_files = WA_MEDIA_PATTERN.findall(message)
    for filename in media_files:
        media_type = _detect_media_type(filename)
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

    def get_adapter_metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="WhatsApp",
            version="1.0.0",
            source="whatsapp",
            doc_url="https://github.com/franklinbaldo/egregora#whatsapp-exports",
            ir_version="v1",
        )

    def parse(
        self,
        input_path: Path,
        *,
        timezone: str | None = None,
        max_chat_bytes: int | None = None,
        **_kwargs: _EmptyKwargs,
    ) -> Table:
        if not input_path.exists():
            msg = f"Input path does not exist: {input_path}"
            raise FileNotFoundError(msg)
        if not input_path.is_file() or not str(input_path).endswith(".zip"):
            msg = f"Expected a ZIP file, got: {input_path}"
            raise ValueError(msg)
        group_name, chat_file = discover_chat_file(input_path)
        _validate_zip_safety(
            input_path,
            chat_file,
            max_bytes=max_chat_bytes or DEFAULT_CHAT_FILE_LIMIT_BYTES,
        )
        export = WhatsAppExport(
            zip_path=input_path,
            group_name=group_name,
            group_slug=GroupSlug(group_name.lower().replace(" ", "-")),
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
            return _convert_whatsapp_media_to_markdown(message)

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
                ext = Path(media_reference).suffix
                from egregora.ops.media import detect_media_type

                media_type = detect_media_type(Path(media_reference))

                return Document(
                    content=file_content,
                    type=DocumentType.MEDIA,
                    metadata={
                        "original_filename": media_reference,
                        "media_type": media_type,
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
        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))
        return {
            "group_name": group_name,
            "group_slug": str(group_slug),
            "chat_file": chat_file,
            "export_date": datetime.now(tz=UTC).date().isoformat(),
        }
