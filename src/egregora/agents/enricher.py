"""Enrichment agent logic for processing URLs and media.

This module implements the enrichment workflow using Pydantic-AI agents.
Refactored to optimize efficient iteration and extract regex.
"""

from __future__ import annotations

import logging
import mimetypes
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
from ibis.expr.types import Table
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.google import GoogleModelSettings

from egregora.config.settings import EnrichmentSettings, get_google_api_key
from egregora.data_primitives.document import Document
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.input_adapters.base import MediaMapping
from egregora.models.google_batch import GoogleBatchModel
from egregora.ops.media import (
    extract_urls,
    find_media_references,
    replace_media_mentions,
)
from egregora.resources.prompts import render_prompt
from egregora.utils.cache import EnrichmentCache, make_enrichment_cache_key
from egregora.utils.datetime_utils import parse_datetime_flexible
from egregora.utils.metrics import UsageTracker
from egregora.utils.paths import slugify
from egregora.utils.quota import QuotaTracker

if TYPE_CHECKING:
    import pandas as pd  # noqa: TID251
    import pyarrow as pa  # noqa: TID251
    from ibis.backends.duckdb import Backend as DuckDBBackend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared Models & Helpers
# ---------------------------------------------------------------------------


def ensure_datetime(value: datetime | str | Any) -> datetime:
    """Convert various datetime representations to Python datetime."""
    parsed = parse_datetime_flexible(value, default_timezone=UTC)
    if parsed is not None:
        return parsed

    msg = f"Unsupported datetime type: {type(value)}"
    raise TypeError(msg)


def load_file_as_binary_content(file_path: Path, max_size_mb: int = 20) -> BinaryContent:
    """Load a file as BinaryContent for pydantic-ai agents."""
    if not file_path.exists():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)
    file_size = file_path.stat().st_size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        size_mb = file_size / (1024 * 1024)
        msg = f"File too large: {size_mb:.2f}MB exceeds {max_size_mb}MB limit. File: {file_path.name}"
        raise ValueError(msg)
    media_type, _ = mimetypes.guess_type(str(file_path))
    if not media_type:
        media_type = "application/octet-stream"
    file_bytes = file_path.read_bytes()
    return BinaryContent(data=file_bytes, media_type=media_type)


def _normalize_slug(candidate: str | None, fallback: str) -> str:
    if isinstance(candidate, str) and candidate.strip():
        value = slugify(candidate.strip())
        if value:
            return value
    return slugify(fallback)


class EnrichmentOutput(BaseModel):
    """Structured output for enrichment agents."""

    slug: str
    markdown: str


# ---------------------------------------------------------------------------
# Dependencies & Contexts
# ---------------------------------------------------------------------------


class UrlEnrichmentDeps(BaseModel):
    """Dependencies for URL enrichment agent."""

    url: str
    prompts_dir: Path | None = None
    original_message: str | None = None
    sender_uuid: str | None = None
    date: str | None = None
    time: str | None = None


class MediaEnrichmentDeps(BaseModel):
    """Dependencies for media enrichment agent."""

    prompts_dir: Path | None = None
    media_type: str | None = None
    media_filename: str | None = None
    media_path: str | None = None
    original_message: str | None = None
    sender_uuid: str | None = None
    date: str | None = None
    time: str | None = None


@dataclass(frozen=True, slots=True)
class EnrichmentRuntimeContext:
    """Runtime context for enrichment execution."""

    cache: EnrichmentCache
    output_format: Any
    site_root: Path | None = None
    duckdb_connection: DuckDBBackend | None = None
    target_table: str | None = None
    quota: QuotaTracker | None = None
    usage_tracker: UsageTracker | None = None
    pii_prevention: dict[str, Any] | None = None
    task_store: Any | None = None


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def _url_enrichment_system_prompt(ctx: RunContext[UrlEnrichmentDeps]) -> str:
    """System prompt constructor for URL enrichment."""
    return render_prompt(
        "enrichment.jinja",
        mode="url",
        prompts_dir=ctx.deps.prompts_dir,
        url=ctx.deps.url,
        original_message=ctx.deps.original_message,
        sender_uuid=ctx.deps.sender_uuid,
        date=ctx.deps.date,
        time=ctx.deps.time,
    )


def create_url_enrichment_agent(model: str) -> Agent[UrlEnrichmentDeps, EnrichmentOutput]:
    """Create URL enrichment agent."""
    model_settings = GoogleModelSettings(google_tools=[{"url_context": {}}])
    model_instance = GoogleBatchModel(api_key=get_google_api_key(), model_name=model)

    agent = Agent[UrlEnrichmentDeps, EnrichmentOutput](
        model=model_instance,
        output_type=EnrichmentOutput,
        model_settings=model_settings,
        system_prompt=_url_enrichment_system_prompt,
    )

    return agent


def _media_enrichment_system_prompt(ctx: RunContext[MediaEnrichmentDeps]) -> str:
    """System prompt constructor for Media enrichment."""
    return render_prompt(
        "enrichment.jinja",
        mode="media",
        prompts_dir=ctx.deps.prompts_dir,
        media_type=ctx.deps.media_type,
        media_filename=ctx.deps.media_filename,
        media_path=ctx.deps.media_path,
        original_message=ctx.deps.original_message,
        sender_uuid=ctx.deps.sender_uuid,
        date=ctx.deps.date,
        time=ctx.deps.time,
    )


def create_media_enrichment_agent(model: str) -> Agent[MediaEnrichmentDeps, EnrichmentOutput]:
    """Create media enrichment agent."""
    model_instance = GoogleBatchModel(api_key=get_google_api_key(), model_name=model)
    agent = Agent[MediaEnrichmentDeps, EnrichmentOutput](
        model=model_instance,
        output_type=EnrichmentOutput,
        system_prompt=_media_enrichment_system_prompt,
    )

    return agent


# ---------------------------------------------------------------------------
# Helper Logic (Internal)
# ---------------------------------------------------------------------------


def _uuid_to_str(value: uuid.UUID | str | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _safe_timestamp_plus_one(timestamp: datetime | pd.Timestamp) -> datetime:
    dt_value = ensure_datetime(timestamp)
    return dt_value + timedelta(seconds=1)


def _create_enrichment_row(
    message_metadata: dict[str, Any] | None,
    enrichment_type: str,
    identifier: str,
    enrichment_id_str: str,
) -> dict[str, Any] | None:
    if not message_metadata:
        return None

    timestamp = message_metadata.get("ts")
    if timestamp is None:
        return None

    timestamp = ensure_datetime(timestamp)
    enrichment_timestamp = _safe_timestamp_plus_one(timestamp)
    enrichment_event_id = str(uuid.uuid4())

    return {
        "event_id": enrichment_event_id,
        "tenant_id": message_metadata.get("tenant_id", ""),
        "source": message_metadata.get("source", ""),
        "thread_id": _uuid_to_str(message_metadata.get("thread_id")),
        "msg_id": f"enrichment-{enrichment_event_id}",
        "ts": enrichment_timestamp,
        "author_raw": "egregora",
        "author_uuid": _uuid_to_str(message_metadata.get("author_uuid")),
        "text": f"[{enrichment_type} Enrichment] {identifier}\nEnrichment saved: {enrichment_id_str}",
        "media_url": None,
        "media_type": None,
        "attrs": {"enrichment_type": enrichment_type, "enrichment_id": enrichment_id_str},
        "pii_flags": None,
        "created_at": message_metadata.get("created_at"),
        "created_by_run": _uuid_to_str(message_metadata.get("created_by_run")),
    }


def _frame_to_records(frame: pd.DataFrame | pa.Table | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert backend frames into dict records consistently."""
    if hasattr(frame, "to_dict"):
        return [dict(row) for row in frame.to_dict("records")]
    if hasattr(frame, "to_pylist"):
        try:
            return [dict(row) for row in frame.to_pylist()]
        except (ValueError, TypeError, AttributeError) as exc:
            msg = f"Failed to convert frame to records. Original error: {exc}"
            raise RuntimeError(msg) from exc
    return [dict(row) for row in frame]


def _iter_table_batches(table: Table, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
    """Stream table rows as batches of dictionaries efficiently.

    Uses `to_pyarrow_batches` if available to avoid full materialization into memory,
    otherwise falls back to batched limits or full execution for smaller tables.
    """
    # Attempt to use pyarrow batches if the backend supports it (DuckDB usually does)
    try:
        if "ts" in table.columns:
             # Ensure deterministic order for batching
             table = table.order_by("ts")

        # Use Ibis to_pyarrow_batches() if available (Ibis 9+)
        # If not, try checking backend capabilities
        # For now, we'll try to execute and if it's huge, we should paginate.
        # But `_iter_table_batches` was specifically called out for "Inefficient Iteration"
        # because it did `table.execute()` (pandas) then convert.

        # Optimized: Use PyArrow batches to avoid Pandas conversion overhead and full memory load
        try:
            # table.to_pyarrow_batches() returns an iterator of RecordBatches
            for batch in table.to_pyarrow_batches(limit=batch_size):
                yield batch.to_pylist()
            return
        except (AttributeError, NotImplementedError):
            pass # Fallback

    except Exception:
        logger.debug("Falling back to pandas execution for enrichment iteration", exc_info=True)

    # Fallback to original implementation if optimization fails
    results_df = table.execute()
    records = _frame_to_records(results_df)
    for start in range(0, len(records), batch_size):
        yield records[start : start + batch_size]


# ---------------------------------------------------------------------------
# Batch Orchestration (Async)
# ---------------------------------------------------------------------------


def schedule_enrichment(
    messages_table: Table,
    media_mapping: MediaMapping,
    enrichment_settings: EnrichmentSettings,
    context: EnrichmentRuntimeContext,
    run_id: uuid.UUID | None = None,
) -> None:
    """Schedule enrichment tasks for background processing."""
    if not hasattr(context, "task_store") or not context.task_store:
        logger.warning("TaskStore not available in context; skipping enrichment scheduling.")
        return

    if messages_table.count().execute() == 0:
        return

    max_enrichments = enrichment_settings.max_enrichments
    enable_url = enrichment_settings.enable_url
    enable_media = enrichment_settings.enable_media

    current_run_id = run_id or uuid.uuid4()

    url_count = 0
    media_count = 0

    # 1. Schedule URL enrichment
    if enable_url:
        url_count = 0
        for batch in _iter_table_batches(messages_table):
            for row in batch:
                if url_count >= max_enrichments:
                    break

                text = row.get("text") or ""
                urls = extract_urls(text)
                for url in urls:
                    if url_count >= max_enrichments:
                        break

                    cache_key = make_enrichment_cache_key(kind="url", identifier=url)
                    if context.cache.load(cache_key) is not None:
                        continue

                    payload = {
                        "type": "url",
                        "url": url,
                        "message_metadata": {
                            "ts": row.get("ts").isoformat() if row.get("ts") else None,
                            "tenant_id": row.get("tenant_id"),
                            "source": row.get("source"),
                            "thread_id": str(row.get("thread_id")),
                            "author_uuid": str(row.get("author_uuid")),
                            "created_at": row.get("created_at").isoformat()
                            if row.get("created_at")
                            else None,
                            "created_by_run": str(row.get("created_by_run")),
                        },
                    }
                    context.task_store.enqueue("enrich_url", payload, current_run_id)
                    url_count += 1

    # 2. Schedule Media enrichment
    if enable_media and media_mapping:
        media_count = 0
        for batch in _iter_table_batches(messages_table):
            for row in batch:
                if media_count >= max_enrichments:
                    break

                text = row.get("text") or ""
                refs = find_media_references(text)
                for ref in refs:
                    if media_count >= max_enrichments:
                        break

                    if ref not in media_mapping:
                        continue

                    media_doc = media_mapping[ref]

                    cache_key = make_enrichment_cache_key(kind="media", identifier=media_doc.document_id)
                    if context.cache.load(cache_key) is not None:
                        continue

                    payload = {
                        "type": "media",
                        "ref": ref,
                        "media_id": media_doc.document_id,
                        "filename": media_doc.metadata.get("filename"),
                        "original_filename": media_doc.metadata.get("original_filename"),
                        "media_type": media_doc.metadata.get("media_type"),
                        "suggested_path": str(media_doc.suggested_path) if media_doc.suggested_path else None,
                        "message_metadata": {
                            "ts": row.get("ts").isoformat() if row.get("ts") else None,
                            "tenant_id": row.get("tenant_id"),
                            "source": row.get("source"),
                            "thread_id": str(row.get("thread_id")),
                            "author_uuid": str(row.get("author_uuid")),
                            "created_at": row.get("created_at").isoformat()
                            if row.get("created_at")
                            else None,
                            "created_by_run": str(row.get("created_by_run")),
                        },
                    }
                    context.task_store.enqueue("enrich_media", payload, current_run_id)
                    media_count += 1

    logger.info(
        "Scheduled %d URL tasks and %d Media tasks",
        url_count if enable_url else 0,
        media_count if enable_media else 0,
    )


def _persist_enrichments(combined: Table, context: EnrichmentRuntimeContext) -> None:
    duckdb_connection = context.duckdb_connection
    target_table = context.target_table

    if (duckdb_connection is None) != (target_table is None):
        msg = "duckdb_connection and target_table must be provided together when persisting"
        raise ValueError(msg)

    if duckdb_connection and target_table:
        try:
            raw_conn = duckdb_connection.con
            storage = DuckDBStorageManager.from_connection(raw_conn)
            storage.persist_atomic(combined, target_table, schema=IR_MESSAGE_SCHEMA)
        except Exception:
            logger.exception("Failed to persist enrichments using DuckDBStorageManager")
            raise


def _replace_pii_media_references(
    messages_table: Table,
    media_mapping: MediaMapping,
) -> Table:
    """Replace media references in messages after PII deletion."""

    @ibis.udf.scalar.python
    def replace_media_udf(text: str) -> str:
        return replace_media_mentions(text, media_mapping) if text else text

    return messages_table.mutate(text=replace_media_udf(messages_table.text))
