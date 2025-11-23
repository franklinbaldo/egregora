"""Formatting utilities for writer module - markdown and table rendering."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC
from pathlib import Path

import pyarrow as pa  # noqa: TID251
from ibis.expr.types import Table
from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.agents.shared.annotations import (
    ANNOTATION_AUTHOR,
    Annotation,
    AnnotationStore,
)
from egregora.data_primitives.document import DocumentType
from egregora.output_adapters.base import OutputSink

logger = logging.getLogger(__name__)


def _load_journal_memory(output_sink: OutputSink) -> str:
    """Return the latest journal memo content (if any)."""
    journals = list(output_sink.list(DocumentType.JOURNAL))
    if not journals:
        return ""

    # Sort by identifier (which contains timestamp YYYY-MM-DD-HH-MM-SS)
    # This is equivalent to sorting by creation time for these files
    latest = max(journals, key=lambda d: d.identifier)

    doc = output_sink.read_document(DocumentType.JOURNAL, latest.identifier)
    return doc.content if doc else ""


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


def _build_conversation_xml(
    data: pa.Table | Iterable[Mapping[str, object]] | Sequence[Mapping[str, object]],
    annotations_store: AnnotationStore | None,
) -> str:
    """Render conversation rows into XML using Jinja2."""
    records, column_order = _table_to_records(data)
    if not records:
        return ""

    rows = [dict(record) for record in records]
    column_order = _ensure_msg_id_column(rows, column_order)

    # Prepare rows for template
    template_rows = []

    # Pre-fetch annotations if store is available
    annotations_map: dict[str, list[Annotation]] = {}
    if annotations_store is not None:
        for row in rows:
            msg_id = row.get("msg_id")
            if msg_id:
                annotations_map[msg_id] = annotations_store.list_annotations_for_message(msg_id)

    for row in rows:
        msg_id = row.get("msg_id", "")
        timestamp_val = row.get("timestamp") or row.get("ts") or ""
        author_val = row.get("author") or row.get("author_uuid") or ""
        text_val = row.get("text") or row.get("message") or ""

        row_data = {
            "msg_id": msg_id,
            "timestamp": _stringify_value(timestamp_val),
            "author": _stringify_value(author_val),
            "text": _stringify_value(text_val),
            "annotations": [],
        }

        if msg_id in annotations_map:
            for ann in annotations_map[msg_id]:
                row_data["annotations"].append(
                    {
                        "id": ann.id,
                        "timestamp": ann.created_at.isoformat(),
                        "author": ANNOTATION_AUTHOR,
                        "commentary": ann.commentary,
                    }
                )

        template_rows.append(row_data)

    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("xml",), default_for_string=True),
    )
    template = env.get_template("conversation.xml.jinja")
    return template.render(rows=template_rows)
