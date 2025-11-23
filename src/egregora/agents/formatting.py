"""Formatting utilities for writer module - markdown and table rendering."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
import pyarrow as pa  # noqa: TID251
from ibis.expr.types import Table
from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.agents.shared.annotations import (
    ANNOTATION_AUTHOR,
    Annotation,
    AnnotationStore,
)

logger = logging.getLogger(__name__)


def _write_journal_markdown(content: str, date: str, output_dir: Path) -> Path:
    """Persist journal LLM responses that skipped tool calls."""
    journal_dir = output_dir / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{date}-freeform"
    candidate_path = journal_dir / f"{base_name}.md"
    suffix = 1
    while candidate_path.exists():
        suffix += 1
        candidate_path = journal_dir / f"{base_name}-{suffix}.md"
    normalized_content = content.strip()
    front_matter = "\n".join(
        ["---", f"title: Journal Response ({date})", f"date: {date}", "---", "", normalized_content, ""]
    )
    candidate_path.write_text(front_matter, encoding="utf-8")
    return candidate_path


def _load_journal_memory(output_dir: Path) -> str:
    """Return the latest journal memo content (if any)."""
    journal_dir = output_dir / "journal"
    if not journal_dir.exists():
        return ""
    files = sorted(journal_dir.glob("*.md"))
    if not files:
        return ""
    latest = max(files, key=lambda path: path.stat().st_mtime)
    try:
        return latest.read_text(encoding="utf-8")
    except OSError:
        return ""


def _stringify_value(value: object) -> str:
    """Convert values to safe strings for table rendering."""
    if isinstance(value, str):
        return value
    pyarrow_na = getattr(pa, "NA", None)
    if value is None or value is pyarrow_na:
        return ""
    if isinstance(value, pa.Scalar):
        return _stringify_value(value.as_py()) if value.is_valid else ""
    try:
        if math.isnan(value):
            return ""
    except TypeError:
        pass
    return str(value)


def _escape_table_cell(value: object) -> str:
    """Escape markdown table delimiters and normalize whitespace."""
    text = _stringify_value(value)
    text = text.replace("|", "\\|")
    return text.replace("\n", "<br>")


def _compute_message_id(row: Mapping[str, object]) -> str:
    """Derive a deterministic identifier for a conversation row.

    Prefers stored message_id field if available, otherwise computes a hash.

    The helper accepts any object exposing ``get`` and ``items`` (for example,
    :class:`dict` as well as mapping-like table rows). Legacy helpers passed both ``(row_index, row)``
    positional arguments, but that form is no longer accepted because the index
    value is ignored during hash computation. The function is private to this
    module, so no downstream backwards compatibility considerations apply.
    """
    if not (hasattr(row, "get") and hasattr(row, "items")):
        msg = "_compute_message_id expects an object with mapping-style access"
        raise TypeError(msg)
    stored_message_id = row.get("message_id")
    if stored_message_id:
        return _stringify_value(stored_message_id)
    parts: list[str] = []
    for key in ("msg_id", "timestamp", "author", "message", "content", "text"):
        value = row.get(key)
        normalized = _stringify_value(value)
        if normalized:
            parts.append(normalized)
    if not parts:
        fallback_pairs = []
        for key, value in sorted(row.items()):
            if key in {"row_index", "similarity"}:
                continue
            normalized = _stringify_value(value)
            if normalized:
                fallback_pairs.append(f"{key}={normalized}")
        if fallback_pairs:
            parts.extend(fallback_pairs)
        else:
            parts.append(json.dumps(row, sort_keys=True, default=_stringify_value))
    raw = "||".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _format_annotations_for_message(annotations: list[Annotation]) -> str:
    """Return formatted annotation text for inclusion in a table cell."""
    if not annotations:
        return ""
    formatted_blocks: list[str] = []
    for annotation in annotations:
        timestamp = (
            annotation.created_at.astimezone(UTC)
            if annotation.created_at.tzinfo
            else annotation.created_at.replace(tzinfo=UTC)
        )
        timestamp_text = timestamp.isoformat().replace("+00:00", "Z")
        parent_note = ""
        if annotation.parent_type == "annotation":
            parent_note = f" · parent #{annotation.parent_id}"
        commentary = _stringify_value(annotation.commentary)
        formatted_blocks.append(
            f"**Annotation #{annotation.id}{parent_note} — {timestamp_text} ({ANNOTATION_AUTHOR})**\n{commentary}"
        )
    return "\n\n".join(formatted_blocks)


def _merge_message_and_annotations(message_value: object, annotations: list[Annotation]) -> str:
    """Append annotation content after the original message text."""
    message_text = _stringify_value(message_value)
    annotations_block = _format_annotations_for_message(annotations)
    if not annotations_block:
        return message_text
    if message_text:
        return f"{message_text}\n\n{annotations_block}"
    return annotations_block


def _build_conversation_xml(
    data: pa.Table | Iterable[Mapping[str, object]] | Sequence[Mapping[str, object]],
    annotations_store: AnnotationStore | None,
) -> str:
    """Render conversation rows into token-efficient XML."""
    records, _ = _table_to_records(data)
    if not records:
        return "<chat></chat>"

    rows = [dict(record) for record in records]
    # Ensure msg_id exists (reuses existing logic)
    _ensure_msg_id_column(rows, ["msg_id", "timestamp", "author", "text"])

    annotations_map: dict[str, list[Annotation]] = {}
    if annotations_store is not None:
        for row in rows:
            msg_id_value = row.get("msg_id")
            if msg_id_value:
                annotations_map[msg_id_value] = annotations_store.list_annotations_for_message(msg_id_value)

    messages = []
    for row in rows:
        msg_id = str(row.get("msg_id", ""))
        author = str(row.get("author", "unknown"))
        ts = str(row.get("timestamp", ""))
        text = str(row.get("text", ""))

        msg_data = {
            "id": msg_id,
            "author": author,
            "ts": ts,
            "content": text,
            "notes": [],
        }

        if msg_id in annotations_map:
            for ann in annotations_map[msg_id]:
                msg_data["notes"].append({"id": ann.id, "content": ann.commentary})
        messages.append(msg_data)

    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["xml", "html", "jinja"]),
    )
    template = env.get_template("conversation.xml.jinja")
    return template.render(messages=messages)


def _table_to_records(
    data: pa.Table | Iterable[Mapping[str, object]] | Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[str]]:
    """Normalize supported tabular inputs into row dictionaries.

    Only :class:`pyarrow.Table` instances or iterables of mapping objects are
    accepted. This keeps the formatting path aligned with Arrow/Ibis-native
    execution without importing pandas at runtime.
    """
    if isinstance(data, pa.Table):
        column_names = [str(name) for name in data.column_names]
        columns = {name: data.column(index).to_pylist() for index, name in enumerate(column_names)}
        records = [
            {name: columns[name][row_index] for name in column_names} for row_index in range(data.num_rows)
        ]
        return (records, column_names)
    if isinstance(data, Mapping):
        msg = "Expected an iterable of mappings, not a single mapping object"
        raise TypeError(msg)
    if isinstance(data, Iterable):
        iter_records: list[dict[str, object]] = []
        iter_column_names: list[str] = []
        for row in data:
            if not isinstance(row, Mapping):
                msg = "Iterable inputs must yield mapping objects"
                raise TypeError(msg)
            normalized = {str(k): v for k, v in row.items()}
            iter_records.append(normalized)
            for key in normalized:
                key_str = str(key)
                if key_str not in iter_column_names:
                    iter_column_names.append(key_str)
        return (iter_records, iter_column_names)
    msg = "Unsupported data source for markdown rendering"
    raise TypeError(msg)


def _ensure_msg_id_column(rows: list[dict[str, object]], column_order: list[str]) -> list[str]:
    """Ensure all rows have msg_id field and return updated column order.

    Prefers stored message_id field, falls back to existing msg_id,
    or computes hash-based IDs as last resort.
    """
    if "msg_id" not in column_order:
        if "message_id" in column_order:
            for row in rows:
                row["msg_id"] = _stringify_value(row.get("message_id"))
        else:
            msg_ids = [_compute_message_id(row) for row in rows]
            for row, msg_id in zip(rows, msg_ids, strict=False):
                row["msg_id"] = msg_id
        return ["msg_id", *column_order]
    for row in rows:
        existing_msg_id = row.get("msg_id")
        if existing_msg_id:
            row["msg_id"] = _stringify_value(existing_msg_id)
        else:
            row["msg_id"] = _stringify_value(row.get("message_id"))
    return column_order


def _build_conversation_markdown_table(
    data: pa.Table | Iterable[Mapping[str, object]] | Sequence[Mapping[str, object]],
    annotations_store: AnnotationStore | None,
) -> str:
    """Render conversation rows into markdown with inline annotations.

    Args:
        data: Conversation rows provided as a :class:`pyarrow.Table` or an
            iterable of mapping objects. Pandas DataFrames are intentionally not
            supported to keep the formatting helpers Arrow/Ibis-native.
        annotations_store: Optional annotation store to append inline notes.

    """
    records, column_order = _table_to_records(data)
    if not records:
        return ""
    rows = [dict(record) for record in records]
    column_order = _ensure_msg_id_column(rows, column_order)
    annotations_map: dict[str, list[Annotation]] = {}
    if annotations_store is not None:
        for row in rows:
            msg_id_value = row.get("msg_id")
            if msg_id_value:
                annotations_map[msg_id_value] = annotations_store.list_annotations_for_message(msg_id_value)
    header = [_escape_table_cell(column) for column in column_order]
    separator = ["---"] * len(column_order)
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(separator) + " |"]
    for row in rows:
        msg_id = row.get("msg_id")
        # IR v1: use "text" column instead of "message"
        message_value = row.get("text", "")
        message_annotations = annotations_map.get(msg_id, []) if msg_id else []
        merged_message = _merge_message_and_annotations(message_value, message_annotations)
        row["text"] = merged_message
        cells = [_escape_table_cell(row.get(column, "")) for column in column_order]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _build_conversation_markdown_verbose(table: Table) -> str:
    """Convert conversation table to markdown string for chunking.

    Supports both CONVERSATION_SCHEMA and IR_MESSAGE_SCHEMA via column detection:
    - timestamp/ts (temporal)
    - author/author_uuid (author identifier)
    - message/text (message content)

    Format:
        ## Message 1
        **Author:** uuid-123
        **Timestamp:** 2025-01-15 10:30:00

        Message text here...

        ## Message 2
        **Author:** uuid-456
        **Timestamp:** 2025-01-15 10:35:00

        Another message...

    Args:
        table: Conversation table (CONVERSATION_SCHEMA or IR_MESSAGE_SCHEMA)

    Returns:
        Markdown-formatted string suitable for chunk_markdown()

    Raises:
        ValueError: If required columns are not found in either schema

    """
    # Detect schema and map column names (CONVERSATION_SCHEMA vs IR_MESSAGE_SCHEMA)
    cols = table.columns

    # Timestamp: 'timestamp' (CONVERSATION) or 'ts' (IR)
    time_col = "timestamp" if "timestamp" in cols else "ts" if "ts" in cols else None

    # Author: 'author' (CONVERSATION) or 'author_uuid' (IR)
    author_col = "author" if "author" in cols else "author_uuid" if "author_uuid" in cols else None

    # Message: 'message' (CONVERSATION) or 'text' (IR)
    message_col = "message" if "message" in cols else "text" if "text" in cols else None

    # Validate required columns exist
    if not time_col or not author_col or not message_col:
        missing = []
        if not time_col:
            missing.append("timestamp/ts")
        if not author_col:
            missing.append("author/author_uuid")
        if not message_col:
            missing.append("message/text")
        msg = f"Table missing required columns: {', '.join(missing)}. Available columns: {', '.join(cols)}"
        raise ValueError(msg)

    # Deterministic ordering
    order_columns: list[object] = [table[time_col]]

    # Add message_id or msg_id for secondary sorting (if available)
    if "message_id" in cols:
        order_columns.append(table["message_id"])
    elif "msg_id" in cols:
        order_columns.append(table["msg_id"])

    ordered_table = table.order_by(order_columns)
    dataframe = ordered_table.select(time_col, author_col, message_col).execute()

    if dataframe.empty:
        return ""

    lines = []
    for idx, row in enumerate(dataframe.itertuples(), start=1):
        lines.append(f"## Message {idx}")
        # Use column position (1, 2, 3) instead of names since select() order is deterministic
        timestamp_val = getattr(row, time_col)
        author_val = getattr(row, author_col)
        message_val = getattr(row, message_col)

        lines.append(f"**Author:** {author_val}")
        lines.append(f"**Timestamp:** {timestamp_val}")
        lines.append("")
        lines.append(message_val)
        lines.append("")

    markdown = "\n".join(lines).strip()
    logger.debug(
        "Consolidated %d messages to markdown (%d chars) using schema: %s/%s/%s",
        len(dataframe),
        len(markdown),
        time_col,
        author_col,
        message_col,
    )
    return markdown
