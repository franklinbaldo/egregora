"""Batch processing utilities for enrichment - dataclasses and helpers."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from google.genai import types as genai_types
from ibis.expr.types import Table

from ...utils import BatchPromptRequest, BatchPromptResult


@dataclass
class UrlEnrichmentJob:
    """Metadata for a URL enrichment batch item."""

    key: Annotated[str, "Unique key for the enrichment job"]
    url: Annotated[str, "The URL to be enriched"]
    original_message: Annotated[str, "The original message containing the URL"]
    sender_uuid: Annotated[str, "The UUID of the message sender"]
    timestamp: Annotated[Any, "The timestamp of the message"]
    path: Annotated[Path, "The path to the original message"]
    tag: Annotated[str, "A tag for identifying the job in batch results"]
    markdown: Annotated[str | None, "The enriched markdown content"] = None
    cached: Annotated[bool, "Whether the result was retrieved from cache"] = False


@dataclass
class MediaEnrichmentJob:
    """Metadata for a media enrichment batch item."""

    key: Annotated[str, "Unique key for the enrichment job"]
    original_filename: Annotated[str, "The original filename of the media"]
    file_path: Annotated[Path, "The path to the media file on disk"]
    original_message: Annotated[str, "The original message containing the media"]
    sender_uuid: Annotated[str, "The UUID of the message sender"]
    timestamp: Annotated[Any, "The timestamp of the message"]
    path: Annotated[Path, "The path to the original message"]
    tag: Annotated[str, "A tag for identifying the job in batch results"]
    media_type: Annotated[str | None, "The type of media (e.g., 'image', 'video')"] = None
    markdown: Annotated[str | None, "The enriched markdown content"] = None
    cached: Annotated[bool, "Whether the result was retrieved from cache"] = False
    upload_uri: Annotated[str | None, "The URI of the uploaded media file"] = None
    mime_type: Annotated[str | None, "The MIME type of the media file"] = None


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
    """Convert an Ibis table to a list of dictionaries without heavy dependencies."""

    to_pylist = getattr(table, "to_pylist", None)
    if callable(to_pylist):
        return list(to_pylist())

    records = table.execute().to_dict("records")
    return [dict(record) for record in records]


def build_batch_requests(
    records: Annotated[list[dict[str, Any]], "A list of prompt records to be converted"],
    model: Annotated[str, "The name of the model to use for the requests"],
    *,
    include_file: Annotated[bool, "Whether to include file data in the requests"] = False,
) -> Annotated[list[BatchPromptRequest], "A list of BatchPromptRequest objects"]:
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
        }

        if not include_file:
            request_kwargs["config"] = genai_types.GenerateContentConfig(temperature=0.3)

        requests.append(BatchPromptRequest(**request_kwargs))

    return requests


def map_batch_results(
    responses: Annotated[list[BatchPromptResult], "A list of BatchPromptResult objects"],
) -> Annotated[
    dict[str | None, BatchPromptResult],
    "A mapping from result tag to the BatchPromptResult",
]:
    """Return a mapping from result tag to the ``BatchPromptResult``."""

    return {result.tag: result for result in responses}
