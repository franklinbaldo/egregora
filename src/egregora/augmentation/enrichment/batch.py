"""Batch processing utilities for enrichment - dataclasses and helpers."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from google.genai import types as genai_types
from ibis.expr.types import Table

from ...utils import BatchPromptRequest, BatchPromptResult


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


def _table_to_pylist(table: Table) -> list[dict[str, Any]]:
    """Convert an Ibis table to a list of dictionaries without heavy dependencies.

    Uses batched iteration to avoid loading entire table into memory at once.
    """
    to_pylist = getattr(table, "to_pylist", None)
    if callable(to_pylist):
        return list(to_pylist())

    # Stream in batches to reduce memory pressure on large tables
    batch_size = 1000
    count = table.count().execute()
    results = []

    for offset in range(0, count, batch_size):
        batch = table.limit(batch_size, offset=offset).execute()
        # Convert batch to records (this is now limited in size)
        batch_records = batch.to_dict("records")
        results.extend(dict(record) for record in batch_records)

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
