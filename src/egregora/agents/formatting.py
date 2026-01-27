"""Formatting utilities for writer module - XML conversation rendering."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.data_primitives.document import DocumentType
from egregora.output_adapters.exceptions import DocumentNotFoundError

if TYPE_CHECKING:
    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.data_primitives.document import Document
    from egregora.output_adapters.base import OutputSink

logger = logging.getLogger(__name__)


def load_journal_memory(output_sink: OutputSink) -> str:
    """Return the latest journal memo content (if any)."""
    journals = list(output_sink.list(DocumentType.JOURNAL))
    if not journals:
        return ""

    # Sort by identifier (which contains timestamp YYYY-MM-DD-HH-MM-SS)
    # This is equivalent to sorting by creation time for these files
    latest = max(journals, key=lambda d: d.identifier)

    try:
        doc = output_sink.get(DocumentType.JOURNAL, latest.identifier)
        return doc.content
    except DocumentNotFoundError:
        return ""


def _stringify_value(value: object) -> str:
    """Convert values to safe strings for conversation rendering."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if hasattr(value, "is_valid") and hasattr(value, "as_py"):
        try:
            return _stringify_value(value.as_py()) if value.is_valid else ""
        except (TypeError, AttributeError):
            return ""
    try:
        if math.isnan(value):
            return ""
    except TypeError:
        pass
    return str(value)


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


class MessageData(TypedDict):
    """TypedDict for message data structure."""

    id: str
    author: str
    ts: str
    content: str
    notes: list[dict[str, str]]


def build_conversation_xml(
    data: Iterable[Mapping[str, object]] | Sequence[Mapping[str, object]],
    annotations_store: AnnotationStore | None,
) -> str:
    """Render conversation rows into token-efficient XML."""
    records, _ = _table_to_records(data)
    if not records:
        return "<chat></chat>"

    rows = [dict(record) for record in records]
    # Ensure msg_id exists (reuses existing logic)
    _ensure_msg_id_column(rows, ["msg_id", "timestamp", "author", "text"])

    annotations_map: dict[str, list[Document]] = {}
    if annotations_store is not None:
        for row in rows:
            msg_id_value = row.get("msg_id")
            if msg_id_value:
                annotations_map[str(msg_id_value)] = annotations_store.list_annotations_for_message(
                    str(msg_id_value)
                )

    messages = []
    for row in rows:
        msg_id = str(row.get("msg_id", ""))
        author = str(row.get("author", "unknown"))
        ts = str(row.get("ts", row.get("timestamp", "")))
        text = str(row.get("text", ""))

        msg_data: MessageData = {
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
    data: Iterable[Mapping[str, object]] | Sequence[Mapping[str, object]] | object,
) -> tuple[list[dict[str, object]], list[str]]:
    """Normalize supported tabular inputs into row dictionaries.

    Accepts iterable/sequence of mapping objects or table-like objects exposing
    Arrow-style attributes (`column_names`, `column`, `num_rows`).
    """
    if hasattr(data, "column_names") and hasattr(data, "column") and hasattr(data, "num_rows"):
        column_names = [str(name) for name in data.column_names]
        columns = {name: data.column(index).to_pylist() for index, name in enumerate(column_names)}
        records = [
            {name: columns[name][row_index] for name in column_names} for row_index in range(data.num_rows)
        ]
        return records, column_names
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
    msg = "Unsupported data source for conversation rendering"
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
