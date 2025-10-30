"""Formatting utilities for writer module - markdown and table rendering."""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import math
import numbers
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC
from functools import lru_cache
from pathlib import Path
from typing import Any, Type, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

import pyarrow as pa

from ..annotations import ANNOTATION_AUTHOR, Annotation, AnnotationStore

logger = logging.getLogger(__name__)


def _write_freeform_markdown(content: str, date: str, output_dir: Path) -> Path:
    """Persist freeform LLM responses that skipped tool calls."""

    freeform_dir = output_dir / "freeform"
    freeform_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{date}-freeform"
    candidate_path = freeform_dir / f"{base_name}.md"
    suffix = 1

    while candidate_path.exists():
        suffix += 1
        candidate_path = freeform_dir / f"{base_name}-{suffix}.md"

    normalized_content = content.strip()
    front_matter = "\n".join(
        [
            "---",
            f"title: Freeform Response ({date})",
            f"date: {date}",
            "---",
            "",
            normalized_content,
            "",
        ]
    )

    candidate_path.write_text(front_matter, encoding="utf-8")
    return candidate_path


def _load_freeform_memory(output_dir: Path) -> str:
    """Return the latest freeform memo content (if any)."""

    freeform_dir = output_dir / "freeform"
    if not freeform_dir.exists():
        return ""

    files = sorted(freeform_dir.glob("*.md"))
    if not files:
        return ""

    latest = max(files, key=lambda path: path.stat().st_mtime)
    try:
        return latest.read_text(encoding="utf-8")
    except OSError:
        return ""


@lru_cache(maxsize=1)
def _pandas_dataframe_type() -> Type[pd.DataFrame] | None:
    """Return the pandas DataFrame type when pandas is available."""

    try:
        pandas_module = importlib.import_module("pandas")
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return None
    return pandas_module.DataFrame


@lru_cache(maxsize=1)
def _pandas_na_singleton() -> Any | None:
    """Return the pandas.NA singleton when pandas is available."""

    try:
        pandas_module = importlib.import_module("pandas")
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return None
    return pandas_module.NA


def _stringify_value(value: Any) -> str:
    """Convert values to safe strings for table rendering."""

    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, pa.Scalar):  # pragma: no branch - defensive conversion
        if not value.is_valid:
            return ""
        return _stringify_value(value.as_py())
    pandas_na = _pandas_na_singleton()
    if pandas_na is not None and value is pandas_na:
        return ""
    if value is getattr(pa, "NA", None):
        return ""
    if isinstance(value, numbers.Real):
        try:
            if math.isnan(value):
                return ""
        except TypeError:  # pragma: no cover - Decimal('NaN') and similar types
            pass
    else:  # pragma: no branch - defensive guard for exotic numeric types
        try:
            if math.isnan(value):
                return ""
        except TypeError:
            pass
    return str(value)


def _escape_table_cell(value: Any) -> str:
    """Escape markdown table delimiters and normalize whitespace."""

    text = _stringify_value(value)
    text = text.replace("|", "\\|")
    return text.replace("\n", "<br>")


def _compute_message_id(row: Any) -> str:
    """Derive a deterministic identifier for a conversation row.

    The helper accepts any object exposing ``get`` and ``items`` (for example,
    :class:`dict` as well as mapping-like table rows). Legacy helpers passed both ``(row_index, row)``
    positional arguments, but that form is no longer accepted because the index
    value is ignored during hash computation. The function is private to this
    module, so no downstream backwards compatibility considerations apply.
    """

    if not (hasattr(row, "get") and hasattr(row, "items")):
        raise TypeError(
            "_compute_message_id expects an object with mapping-style access"
        )

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
            parts.append(
                json.dumps(row, sort_keys=True, default=_stringify_value)
            )

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
        parent_note = (
            f" · parent #{annotation.parent_annotation_id}"
            if getattr(annotation, "parent_annotation_id", None) is not None
            else ""
        )
        commentary = _stringify_value(annotation.commentary)
        formatted_blocks.append(
            f"**Annotation #{annotation.id}{parent_note} — {timestamp_text} ({ANNOTATION_AUTHOR})**"
            f"\n{commentary}"
        )

    return "\n\n".join(formatted_blocks)


def _merge_message_and_annotations(message_value: Any, annotations: list[Annotation]) -> str:
    """Append annotation content after the original message text."""

    message_text = _stringify_value(message_value)
    annotations_block = _format_annotations_for_message(annotations)

    if not annotations_block:
        return message_text
    if message_text:
        return f"{message_text}\n\n{annotations_block}"
    return annotations_block


def _table_to_records(
    data: pa.Table | Iterable[Mapping[str, Any]] | Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize heterogeneous tabular inputs into row dictionaries."""

    if isinstance(data, pa.Table):
        column_names = [str(name) for name in data.column_names]
        columns = {
            name: data.column(index).to_pylist()
            for index, name in enumerate(column_names)
        }
        records = [
            {name: columns[name][row_index] for name in column_names}
            for row_index in range(data.num_rows)
        ]
        return records, column_names

    dataframe_type = _pandas_dataframe_type()
    if dataframe_type is not None and isinstance(data, dataframe_type):
        df_column_names = [str(column) for column in data.columns]
        df_records = [{str(k): v for k, v in record.items()} for record in data.to_dict("records")]
        return df_records, df_column_names

    if isinstance(data, Iterable):
        iter_records = [{str(k): v for k, v in row.items()} for row in data]
        iter_column_names: list[str] = []
        for record in iter_records:
            for key in record:
                if key not in iter_column_names:
                    iter_column_names.append(str(key))
        return iter_records, iter_column_names

    raise TypeError("Unsupported data source for markdown rendering")


def _build_conversation_markdown(
    data: pa.Table | Iterable[Mapping[str, Any]] | Sequence[Mapping[str, Any]],
    annotations_store: AnnotationStore | None,
) -> str:
    """Render conversation rows into markdown with inline annotations."""

    records, column_order = _table_to_records(data)
    if not records:
        return ""

    rows = [dict(record) for record in records]

    if "msg_id" not in column_order:
        msg_ids = [_compute_message_id(row) for row in rows]
        column_order = ["msg_id", *column_order]
        for row, msg_id in zip(rows, msg_ids, strict=False):
            row["msg_id"] = msg_id
    else:
        for row in rows:
            row["msg_id"] = _stringify_value(row.get("msg_id"))

    annotations_map: dict[str, list[Annotation]] = {}
    if annotations_store is not None:
        for row in rows:
            msg_id_value = row.get("msg_id")
            if msg_id_value:
                annotations_map[msg_id_value] = annotations_store.get_annotations_for_message(
                    msg_id_value
                )

    header = [_escape_table_cell(column) for column in column_order]
    separator = ["---"] * len(column_order)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]

    for row in rows:
        msg_id = row.get("msg_id")
        message_value = row.get("message", "")
        message_annotations = annotations_map.get(msg_id, []) if msg_id else []

        merged_message = _merge_message_and_annotations(message_value, message_annotations)
        row["message"] = merged_message

        cells = [_escape_table_cell(row.get(column, "")) for column in column_order]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)
