"""Batch processing utilities for enrichment - dataclasses and helpers."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from google.genai import types as genai_types
from ibis.expr.types import Table

from egregora.utils import BatchPromptRequest, BatchPromptResult

if TYPE_CHECKING:
    import pandas as pd
    import pyarrow as pa


@dataclass
class UrlEnrichmentJob:
    """Metadata for a URL enrichment batch item."""

    key: str
    url: str
    original_message: str
    sender_uuid: str
    timestamp: Any
    path: Path
    tag: str
    markdown: str | None = None
    cached: bool = False


@dataclass
class MediaEnrichmentJob:
    """Metadata for a media enrichment batch item."""

    key: str
    original_filename: str
    file_path: Path
    original_message: str
    sender_uuid: str
    timestamp: Any
    path: Path
    tag: str
    media_type: str | None = None
    markdown: str | None = None
    cached: bool = False
    upload_uri: str | None = None
    mime_type: str | None = None


def _ensure_datetime(value: datetime | pd.Timestamp) -> datetime:
    """Convert pandas/ibis timestamp objects to ``datetime``."""
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


def _safe_timestamp_plus_one(timestamp: datetime | pd.Timestamp) -> datetime:
    """Return timestamp + 1 second, handling pandas/ibis types."""
    dt_value = _ensure_datetime(timestamp)
    return dt_value + timedelta(seconds=1)


def _frame_to_records(frame: pd.DataFrame | pa.Table | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert backend frames into dict records consistently."""
    if hasattr(frame, "to_dict"):
        return [dict(row) for row in frame.to_dict("records")]
    if hasattr(frame, "to_pylist"):
        try:
            return [dict(row) for row in frame.to_pylist()]
        except (ValueError, TypeError, AttributeError) as e:
            msg = f"Failed to convert frame to records. Original error: {e}"
            raise RuntimeError(msg) from e
    if isinstance(frame, list):
        return [dict(row) for row in frame]
    return [dict(row) for row in frame]


def _iter_table_record_batches(table: Table, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
    """Stream table rows as batches of dictionaries without loading entire table into memory.

    Uses PyArrow's streaming capabilities to iterate through table in fixed-size batches,
    enabling memory-efficient processing of arbitrarily large windows.

    Args:
        table: Ibis table expression to stream
        batch_size: Number of rows per batch (advisory, actual batch size may vary)

    Yields:
        Lists of dictionaries representing rows (up to batch_size per batch)

    Note:
        PyArrow RecordBatch sizes are determined by the backend, so actual batches
        may be larger or smaller than batch_size. We slice them to target size.

    """
    # Order by timestamp for deterministic iteration
    if "timestamp" in table.columns:
        table = table.order_by("timestamp")

    # Stream table as PyArrow RecordBatches (memory-efficient)
    try:
        record_batch_reader = table.to_pyarrow_batches()
    except (AttributeError, NotImplementedError):
        # Fallback for backends without streaming support
        df = table.execute()
        records = _frame_to_records(df)
        for start in range(0, len(records), batch_size):
            yield records[start : start + batch_size]
        return

    # Process RecordBatches in streaming fashion
    buffer: list[dict[str, Any]] = []

    for record_batch in record_batch_reader:
        # Convert RecordBatch to list of dicts
        batch_dicts = record_batch.to_pylist()
        buffer.extend(batch_dicts)

        # Yield full batches when buffer reaches target size
        while len(buffer) >= batch_size:
            yield buffer[:batch_size]
            buffer = buffer[batch_size:]

    # Yield remaining records
    if buffer:
        yield buffer


def _table_to_pylist(table: Table) -> list[dict[str, Any]]:
    """Convert an Ibis table to a list of dictionaries without heavy dependencies."""
    results: list[dict[str, Any]] = []
    for batch in _iter_table_record_batches(table):
        results.extend(batch)
    return results


def build_batch_requests(
    records: list[dict[str, Any]], model: str, *, include_file: bool = False
) -> list[BatchPromptRequest]:
    """Convert prompt records into ``BatchPromptRequest`` objects."""
    requests: list[BatchPromptRequest] = []
    for record in records:
        parts = [genai_types.Part(text=record["prompt"])]
        if include_file:
            file_uri = record.get("file_uri")
            if file_uri:
                parts.append(
                    genai_types.Part(
                        file_data=genai_types.FileData(
                            file_uri=file_uri, mime_type=record.get("mime_type", "application/octet-stream")
                        )
                    )
                )
        request_kwargs: dict[str, Any] = {
            "contents": [genai_types.Content(role="user", parts=parts)],
            "model": model,
            "tag": record.get("tag"),
            "config": genai_types.GenerateContentConfig(temperature=0.3, top_k=40, top_p=0.95),
        }
        requests.append(BatchPromptRequest(**request_kwargs))
    return requests


def map_batch_results(responses: list[BatchPromptResult]) -> dict[str | None, BatchPromptResult]:
    """Return a mapping from result tag to the ``BatchPromptResult``."""
    return {result.tag: result for result in responses}
