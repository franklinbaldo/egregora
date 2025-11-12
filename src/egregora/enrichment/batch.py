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
    """Yield batches of table rows as dictionaries.

    Simplified implementation for Egregora's typical use case: window sizes of
    100-1000 messages that easily fit in memory. No streaming complexity needed.

    Args:
        table: Ibis table expression to execute
        batch_size: Number of rows per batch

    Yields:
        Lists of dictionaries representing rows

    """
    # Order by timestamp if available for deterministic iteration
    if "timestamp" in table.columns:
        table = table.order_by("timestamp")

    # Execute table and convert to records
    df = table.execute()
    records = _frame_to_records(df)

    # Yield in batches
    for start in range(0, len(records), batch_size):
        yield records[start : start + batch_size]


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
