"""Batch processing utilities for enrichment - dataclasses and helpers."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import ibis
from google.genai import types as genai_types
from ibis.expr.types import Table

from egregora.streaming import ensure_deterministic_order, stream_ibis
from egregora.utils import BatchPromptRequest, BatchPromptResult


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


def _ensure_datetime(value: Any) -> datetime:
    """Convert pandas/ibis timestamp objects to ``datetime``."""
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


def _safe_timestamp_plus_one(timestamp: Any) -> Any:
    """Return timestamp + 1 second, handling pandas/ibis types."""
    dt_value = _ensure_datetime(timestamp)
    return dt_value + timedelta(seconds=1)


_STABLE_ORDER_CANDIDATES: tuple[str, ...] = (
    "timestamp",
    "created_at",
    "datetime",
    "date",
    "ts",
    "time",
    "id",
    "uuid",
    "key",
)


def _get_stable_ordering(table: Table) -> list:
    """Return a deterministic ordering for ``table`` when batching rows."""

    columns = list(table.columns)
    for candidate in _STABLE_ORDER_CANDIDATES:
        if candidate in columns:
            return [table[candidate]]

    if columns:
        return [table[column] for column in columns]

    return []


def _frame_to_records(frame: Any) -> list[dict[str, Any]]:
    """Convert backend frames into ``dict`` records consistently.

    Note: This is legacy fallback code. Most code paths should now use
    stream_ibis from egregora.data instead, which handles timezones correctly.
    """

    if hasattr(frame, "to_dict"):
        return [dict(row) for row in frame.to_dict("records")]
    if hasattr(frame, "to_pylist"):
        try:
            return [dict(row) for row in frame.to_pylist()]
        except Exception as e:
            # PyArrow can fail with timezone-aware timestamps
            # This should rarely be hit since stream_ibis (above) handles it
            raise RuntimeError(
                "Failed to convert frame to records. "
                "This indicates the stream_ibis fast path was not used. "
                f"Original error: {e}"
            ) from e
    if isinstance(frame, list):
        return [dict(row) for row in frame]

    return [dict(row) for row in frame]


def _iter_table_record_batches(
    table: Table, batch_size: int = 1000
) -> Iterator[list[dict[str, Any]]]:
    """Yield batches of table rows as dictionaries in a deterministic order.

    This function now uses egregora.data.stream_ibis for memory-efficient streaming
    without materializing the full table. This fixes Bug #3 (timezone-aware timestamps).

    Args:
        table: Ibis table expression to stream
        batch_size: Number of rows per batch

    Yields:
        Lists of dictionaries representing rows

    Note:
        Uses the table's backend connection automatically via Ibis's
        _find_backend() method.
    """
    # Try to get the backend connection from the table
    try:
        backend = table._find_backend()
        if backend is not None:
            # Use new stream_ibis utility - handles timezones correctly
            ordered_table = ensure_deterministic_order(table)
            yield from stream_ibis(ordered_table, backend, batch_size=batch_size)
            return
    except (AttributeError, Exception):
        # Backend not available or stream_ibis failed - fall back to legacy approach
        pass

    # Legacy fallback: Use Ibis windowing for deterministic batching
    # This approach still works but requires more execute() calls
    count = table.count().execute()
    if not count:
        return

    ordering = _get_stable_ordering(table)
    fallback_ordering = ordering or [table[column] for column in table.columns]

    if not fallback_ordering:
        # Degenerate table (no columns) – just execute once and chunk locally
        dataframe = table.execute()
        records = _frame_to_records(dataframe)
        if not records:
            return
        for start in range(0, len(records), batch_size):
            yield records[start : start + batch_size]
        return

    ordered_table = table.order_by(fallback_ordering)
    window = ibis.window(order_by=fallback_ordering)
    numbered = ordered_table.mutate(
        _batch_row_number=ibis.row_number().over(window)
    )
    row_number = numbered._batch_row_number

    for start in range(0, count, batch_size):
        upper = start + batch_size
        batch_expr = numbered.filter(
            ((row_number >= start) & (row_number < upper))
            if start
            else (row_number < upper)
        ).order_by(row_number)
        # Drop helper column only after enforcing deterministic ordering
        batch_expr = batch_expr.drop("_batch_row_number")
        dataframe = batch_expr.execute()
        batch_records = _frame_to_records(dataframe)
        if not batch_records:
            continue
        yield batch_records


def _table_to_pylist(table: Table) -> list[dict[str, Any]]:
    """Convert an Ibis table to a list of dictionaries without heavy dependencies."""

    results: list[dict[str, Any]] = []
    for batch in _iter_table_record_batches(table):
        results.extend(batch)
    return results


def build_batch_requests(
    records: list[dict[str, Any]],
    model: str,
    *,
    include_file: bool = False,
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
                            file_uri=file_uri,
                            mime_type=record.get("mime_type", "application/octet-stream"),
                        )
                    )
                )

        request_kwargs: dict[str, Any] = {
            "contents": [genai_types.Content(role="user", parts=parts)],
            "model": model,
            "tag": record.get("tag"),
            # Always provide explicit config for deterministic behavior across text and vision
            "config": genai_types.GenerateContentConfig(
                temperature=0.3,
                top_k=40,
                top_p=0.95,
            ),
        }

        requests.append(BatchPromptRequest(**request_kwargs))

    return requests


def map_batch_results(
    responses: list[BatchPromptResult],
) -> dict[str | None, BatchPromptResult]:
    """Return a mapping from result tag to the ``BatchPromptResult``."""

    return {result.tag: result for result in responses}
