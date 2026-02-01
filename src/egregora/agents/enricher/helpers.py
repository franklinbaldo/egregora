"""Helper functions for enrichment."""

from __future__ import annotations

import logging
import mimetypes
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from ibis.common.exceptions import IbisError
from pydantic_ai import RunContext
from pydantic_ai.messages import BinaryContent

from egregora.agents.exceptions import (
    EnrichmentFileError,
    EnrichmentSlugError,
    JinaFetchError,
)
from egregora.data_primitives.datetime_utils import ensure_datetime
from egregora.data_primitives.text import slugify
from egregora.database.streaming import ensure_deterministic_order, stream_ibis

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ibis.expr.types import Table

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 10  # Seconds for heartbeat logging
_MARKDOWN_LINK_PATTERN = re.compile(r"(?:!\[|\[)[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")
_UUID_PATTERN = re.compile(r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.\w+)")


def load_file_as_binary_content(file_path: Path, max_size_mb: int = 20) -> BinaryContent:
    """Load a file as BinaryContent for pydantic-ai agents."""
    if not file_path.exists():
        msg = f"File not found: {file_path}"
        raise EnrichmentFileError(msg)
    file_size = file_path.stat().st_size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        size_mb = file_size / (1024 * 1024)
        msg = f"File too large: {size_mb:.2f}MB exceeds {max_size_mb}MB limit. File: {file_path.name}"
        raise EnrichmentFileError(msg)
    media_type, _ = mimetypes.guess_type(str(file_path))
    if not media_type:
        media_type = "application/octet-stream"
    file_bytes = file_path.read_bytes()
    return BinaryContent(data=file_bytes, media_type=media_type)


def normalize_slug(candidate: str | None, identifier: str) -> str:
    """Normalize a slug candidate from LLM output.

    Args:
        candidate: Slug string from LLM (may be None or empty)
        identifier: Original identifier (URL or filename) for error messages

    Returns:
        Normalized, valid slug string

    Raises:
        ValueError: If candidate is None, empty, or doesn't produce a valid slug

    """
    if not isinstance(candidate, str) or not candidate.strip():
        msg = f"LLM failed to generate slug for: {identifier[:100]}"
        raise EnrichmentSlugError(msg)

    value = slugify(candidate.strip())
    if not value or value == "post":
        msg = f"LLM slug '{candidate}' is invalid after normalization for: {identifier[:100]}"
        raise EnrichmentSlugError(msg)

    return value


async def fetch_url_with_jina(ctx: RunContext[Any], url: str) -> str:
    """Fetch URL content using Jina.ai Reader.

    Use this tool ONLY if the standard 'WebFetchTool' fails to retrieve meaningful content.
    Examples of when to use this:
    - The standard fetch returns "JavaScript is required" or "Access Denied" (403/429).
    - The content is empty or contains only cookie/GDPR banners.
    - The page is a Single Page Application (SPA) that didn't render.
    """
    jina_url = f"https://r.jina.ai/{url}"

    # Headers to enable image captioning and ensure JSON response if needed
    headers = {"X-With-Generated-Alt": "true", "X-Retain-Images": "none"}

    async with httpx.AsyncClient() as client:
        try:
            # Jina returns Markdown by default
            response = await client.get(jina_url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            msg = f"Jina fetch failed: {exc}"
            raise JinaFetchError(msg) from exc


def uuid_to_str(value: uuid.UUID | str | None) -> str | None:
    """Convert UUID to string if not None."""
    if value is None:
        return None
    return str(value)


def safe_timestamp_plus_one(timestamp: datetime | str | Any) -> datetime:
    """Ensure timestamp is valid and add one second."""
    dt_value = ensure_datetime(timestamp)
    return dt_value + timedelta(seconds=1)


def create_enrichment_row(
    message_metadata: dict[str, Any] | None,
    enrichment_type: str,
    identifier: str,
    enrichment_id_str: str,
    media_identifier: str | None = None,
) -> dict[str, Any] | None:
    """Create a new row for the enrichment event in the messages table."""
    if not message_metadata:
        return None

    timestamp = message_metadata.get("ts")
    if timestamp is None:
        return None

    timestamp = ensure_datetime(timestamp)
    enrichment_timestamp = safe_timestamp_plus_one(timestamp)
    enrichment_event_id = str(uuid.uuid4())

    return {
        "event_id": enrichment_event_id,
        "tenant_id": message_metadata.get("tenant_id", ""),
        "source": message_metadata.get("source", ""),
        "thread_id": uuid_to_str(message_metadata.get("thread_id")),
        "msg_id": f"enrichment-{enrichment_event_id}",
        "ts": enrichment_timestamp,
        "author_raw": "egregora",
        "author_uuid": uuid_to_str(message_metadata.get("author_uuid")),
        "text": f"[{enrichment_type} Enrichment] {identifier}\nEnrichment saved: {enrichment_id_str}",
        "media_url": media_identifier,
        "media_type": enrichment_type,
        "attrs": {
            "enrichment_type": enrichment_type,
            "enrichment_id": enrichment_id_str,
        },
        "pii_flags": None,
        "created_at": message_metadata.get("created_at"),
        "created_by_run": uuid_to_str(message_metadata.get("created_by_run")),
    }


def frame_to_records(frame: Any) -> list[dict[str, Any]]:
    """Convert backend frames into dict records consistently."""
    if hasattr(frame, "to_dict"):
        return [dict(row) for row in frame.to_dict("records")]
    if hasattr(frame, "to_pylist"):
        try:
            return [dict(row) for row in frame.to_pylist()]
        except (
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:  # pragma: no cover - defensive
            msg = f"Failed to convert frame to records. Original error: {exc}"
            raise RuntimeError(msg) from exc
    return [dict(row) for row in frame]


def iter_table_batches(table: Table, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
    """Stream table rows as batches of dictionaries without loading entire table into memory."""
    try:
        backend = table._find_backend()
    except (AttributeError, IbisError):  # pragma: no cover - fallback path
        backend = None

    if backend is not None and hasattr(backend, "con"):
        ordered_table = ensure_deterministic_order(table)
        yield from stream_ibis(ordered_table, backend, batch_size=batch_size)
        return

    if "ts" in table.columns:
        table = table.order_by("ts")

    results_df = table.execute()
    records = frame_to_records(results_df)
    for start in range(0, len(records), batch_size):
        yield records[start : start + batch_size]
