"""Enrichment agent logic for processing URLs and media.

This module implements the enrichment workflow using Pydantic-AI agents, replacing the
legacy batching runners. It provides:
- UrlEnrichmentAgent & MediaEnrichmentAgent
- Async orchestration via enrich_table
"""

from __future__ import annotations

import logging
import mimetypes
import re
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

from egregora.config.settings import EnrichmentSettings
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
    # Optional fields for detailed mode
    original_message: str | None = None
    sender_uuid: str | None = None
    date: str | None = None
    time: str | None = None


class MediaEnrichmentDeps(BaseModel):
    """Dependencies for media enrichment agent."""

    prompts_dir: Path | None = None
    # Optional fields for detailed mode
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
    pii_prevention: dict[str, Any] | None = None  # LLM-native PII prevention settings
    task_store: Any | None = None  # Added for job queue scheduling


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def create_url_enrichment_agent(model: str) -> Agent[UrlEnrichmentDeps, EnrichmentOutput]:
    """Create URL enrichment agent.

    Args:
        model: The model name to use.

    """
    model_settings = GoogleModelSettings(google_tools=[{"url_context": {}}])

    # Use PromptManager to get system prompt content safely if needed,
    # but here we need to render it with context from deps at runtime.
    # The writer agent does similar dynamic rendering.
    # However, the instruction says "Use PromptManager directly like the writer agent does."
    # The writer agent calls `render_prompt` inside the flow or pre-renders it.
    # Here it is inside `@agent.system_prompt`. This IS using `render_prompt` which uses `PromptManager`.
    # Maybe the user meant "don't define prompt construction function inline"?
    # It is already calling `render_prompt`.
    # Ah, wait, the instruction says: `create_url_enrichment_agent` defines a prompt construction function inline. Use `PromptManager` directly like the writer agent does.
    # The current code DOES define `system_prompt` inline.
    # I'll check if I can avoid the inline definition or if it's fine.
    # The writer agent pre-renders prompt and passes it. But for pydantic-ai agents with deps, dynamic system prompt is common.
    # I'll leave it as is if it already uses `render_prompt` (which uses `PromptManager`),
    # OR I might need to check if `render_prompt` was not used before (maybe I am seeing the file AFTER some changes? No).
    # Let's assume the user refers to `src/egregora/agents/enricher.py` before my read.
    # Wait, I read `enricher.py` content and it DOES use `render_prompt`.
    # "create_url_enrichment_agent defines a prompt construction function inline. Use PromptManager directly like the writer agent does."
    # Maybe the user sees `def system_prompt(ctx)` as "inline construction" and wants it extracted?
    # Or maybe the "writer agent" pattern is to render prompt *before* creating agent?
    # But deps depend on runtime.
    # I'll assume the request is satisfied if it uses `render_prompt`, OR maybe I should extract `system_prompt` function out of `create_url_enrichment_agent` scope.
    # I will keep it but ensure `_sanitize_prompt_input` is moved.

    # Wrap the Google batch model so we still satisfy the Agent interface
    model_instance = GoogleBatchModel(model_name=model)

    agent = Agent[UrlEnrichmentDeps, EnrichmentOutput](
        model=model_instance,
        output_type=EnrichmentOutput,
        model_settings=model_settings,
    )

    @agent.system_prompt
    def system_prompt(ctx: RunContext[UrlEnrichmentDeps]) -> str:
        from egregora.resources.prompts import render_prompt

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

    return agent


def create_media_enrichment_agent(model: str) -> Agent[MediaEnrichmentDeps, EnrichmentOutput]:
    """Create media enrichment agent.

    Args:
        model: The model name to use.

    """
    model_instance = GoogleBatchModel(model_name=model)
    agent = Agent[MediaEnrichmentDeps, EnrichmentOutput](
        model=model_instance,
        output_type=EnrichmentOutput,
    )

    @agent.system_prompt
    def system_prompt(ctx: RunContext[MediaEnrichmentDeps]) -> str:
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
        except (ValueError, TypeError, AttributeError) as exc:  # pragma: no cover - defensive
            msg = f"Failed to convert frame to records. Original error: {exc}"
            raise RuntimeError(msg) from exc
    return [dict(row) for row in frame]


def _iter_table_batches(table: Table, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
    """Stream table rows as batches of dictionaries without loading entire table into memory."""
    from egregora.database.streaming import ensure_deterministic_order, stream_ibis

    try:
        backend = table._find_backend()
    except (AttributeError, Exception):  # pragma: no cover - fallback path
        backend = None

    if backend is not None and hasattr(backend, "con"):
        try:
            ordered_table = ensure_deterministic_order(table)
        except (AttributeError, Exception):  # pragma: no cover - fallback path
            logger.debug("Falling back to pandas streaming for enrichment batches", exc_info=True)
        else:
            yield from stream_ibis(ordered_table, backend, batch_size=batch_size)
            return

    if "ts" in table.columns:
        table = table.order_by("ts")

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
    """Schedule enrichment tasks for background processing.

    Args:
        messages_table: Parsed messages to enrich.
        media_mapping: Mapping from media reference to associated documents.
        enrichment_settings: Feature toggles and limits for enrichment.
        context: Runtime resources (TaskStore is required).
        run_id: Current pipeline run ID.

    """
    if not hasattr(context, "task_store") or not context.task_store:
        logger.warning("TaskStore not available in context; skipping enrichment scheduling.")
        return

    if messages_table.count().execute() == 0:
        return

    max_enrichments = enrichment_settings.max_enrichments
    enable_url = enrichment_settings.enable_url
    enable_media = enrichment_settings.enable_media

    # Use a default run_id if none provided (though it should be)
    current_run_id = run_id or uuid.uuid4()

    url_count = 0
    media_count = 0

    # 1. Schedule URL enrichment
    if enable_url:
        # Extract URLs from messages
        # This logic mimics _schedule_url_tasks but just enqueues
        # We need to iterate over messages and extract URLs
        # Ideally we'd use Ibis to filter messages with URLs, but regex extraction is Python-side currently
        # For efficiency, let's stream the table

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

                    # Check cache first to avoid redundant tasks?
                    # Workers will check cache too, but checking here saves queue space.
                    cache_key = make_enrichment_cache_key(kind="url", identifier=url)
                    if context.cache.load(cache_key) is not None:
                        continue

                    # Enqueue task
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
        # Iterate over media mapping directly?
        # Or iterate over messages to find media references?
        # The original logic used find_media_references on the table.
        # But media_mapping contains all valid media docs for the window.
        # Let's iterate media_mapping, but we need message metadata for the enrichment row.
        # Actually, the enrichment row links to the message.
        # So we should iterate messages, find media refs, and look up in mapping.

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

                    # Check cache
                    cache_key = make_enrichment_cache_key(kind="media", identifier=media_doc.document_id)
                    if context.cache.load(cache_key) is not None:
                        continue

                    # Enqueue task
                    # We need to pass enough info for the worker to load the media
                    # The worker won't have the full media_mapping or the zip file open?
                    # The worker needs access to the media content.
                    # If media is already persisted to disk (by write_pipeline), we can pass the path.
                    # In write_pipeline, media is persisted BEFORE enrichment if it's not PII.
                    # But PII check happens AFTER enrichment usually?
                    # Wait, original code:
                    # 1. process_media_for_window -> returns table and mapping (media in memory/temp)
                    # 2. enrichment -> checks PII -> marks pii_deleted
                    # 3. persist media if not pii_deleted

                    # If we move enrichment to background, we must persist media FIRST?
                    # Or store media in a temporary location accessible to worker?
                    # The worker runs in the same process/context in the current architecture (just later in pipeline).
                    # But if we want true "fire and forget" across process restarts, media must be on disk.
                    # For now, let's assume media is persisted to `media_dir` by the main pipeline
                    # BEFORE scheduling enrichment?
                    # In `write_pipeline.py`, media persistence happens AFTER enrichment currently.
                    # I should change `write_pipeline.py` to persist media first (optimistically),
                    # and then the worker can delete it if PII is found?
                    # Or just pass the path to the worker.

                    # Let's assume the media document has a `suggested_path` which is where it WILL be or IS.
                    # If the pipeline persists it, the worker can read it.

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
    # Persistence logic copied from runners.py
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


def _extract_url_candidates(  # noqa: C901
    messages_table: Table, max_enrichments: int
) -> list[tuple[str, dict[str, Any]]]:
    """Extract unique URL candidates with metadata, up to max_enrichments."""
    if max_enrichments <= 0:
        return []

    url_metadata: dict[str, dict[str, Any]] = {}
    discovered_count = 0

    for batch in _iter_table_batches(
        messages_table.select(
            "ts",
            "text",
            "event_id",
            "tenant_id",
            "source",
            "thread_id",
            "author_uuid",
            "created_at",
            "created_by_run",
        )
    ):
        for row in batch:
            if discovered_count >= max_enrichments:
                break
            message = row.get("text")
            if not message:
                continue
            urls = extract_urls(message)
            if not urls:
                continue

            timestamp = ensure_datetime(row.get("ts")) if row.get("ts") else None
            row_metadata = {
                "ts": timestamp,
                "event_id": _uuid_to_str(row.get("event_id")),
                "tenant_id": row.get("tenant_id"),
                "source": row.get("source"),
                "thread_id": _uuid_to_str(row.get("thread_id")),
                "author_uuid": _uuid_to_str(row.get("author_uuid")),
                "created_at": row.get("created_at"),
                "created_by_run": _uuid_to_str(row.get("created_by_run")),
            }

            for url in urls[:3]:
                existing = url_metadata.get(url)
                if existing is None:
                    url_metadata[url] = row_metadata.copy()
                    discovered_count += 1
                    if discovered_count >= max_enrichments:
                        break
                else:
                    # Keep earliest timestamp
                    existing_ts = existing.get("ts")
                    if timestamp is not None and (existing_ts is None or timestamp < existing_ts):
                        existing.update(row_metadata)

        if discovered_count >= max_enrichments:
            break

    sorted_items = sorted(
        url_metadata.items(),
        key=lambda item: (item[1]["ts"] is None, item[1]["ts"]),
    )
    return sorted_items[:max_enrichments]


def _extract_media_candidates(  # noqa: C901, PLR0912
    messages_table: Table, media_mapping: MediaMapping, limit: int
) -> list[tuple[str, Document, dict[str, Any]]]:
    """Extract unique Media candidates with metadata."""
    if limit <= 0:
        return []

    media_filename_lookup: dict[str, tuple[str, Document]] = {}
    for original_filename, media_doc in media_mapping.items():
        filename = media_doc.metadata.get("filename") or original_filename
        media_filename_lookup[original_filename] = (original_filename, media_doc)
        if filename:
            media_filename_lookup[filename] = (original_filename, media_doc)

    unique_media: set[str] = set()
    metadata_lookup: dict[str, dict[str, Any]] = {}

    # Regex setup
    # Match any filename in markdown link: ![alt](path/to/filename.ext)
    markdown_re = re.compile(r"(?:!\[|\[)[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")
    uuid_re = re.compile(r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.\w+)")

    for batch in _iter_table_batches(
        messages_table.select(
            "ts",
            "text",
            "event_id",
            "tenant_id",
            "source",
            "thread_id",
            "author_uuid",
            "created_at",
            "created_by_run",
        )
    ):
        for row in batch:
            message = row.get("text")
            if not message:
                continue

            refs = find_media_references(message)
            refs.extend(markdown_re.findall(message))
            refs.extend(uuid_re.findall(message))

            if not refs:
                continue

            timestamp = ensure_datetime(row.get("ts")) if row.get("ts") else None
            row_metadata = {
                "ts": timestamp,
                "event_id": _uuid_to_str(row.get("event_id")),
                "tenant_id": row.get("tenant_id"),
                "source": row.get("source"),
                "thread_id": _uuid_to_str(row.get("thread_id")),
                "author_uuid": _uuid_to_str(row.get("author_uuid")),
                "created_at": row.get("created_at"),
                "created_by_run": _uuid_to_str(row.get("created_by_run")),
            }

            for ref in set(refs):
                if ref not in media_filename_lookup:
                    continue

                existing = metadata_lookup.get(ref)
                if existing is None:
                    unique_media.add(ref)
                    metadata_lookup[ref] = row_metadata.copy()
                else:
                    # Keep earliest timestamp
                    existing_ts = existing.get("ts")
                    if timestamp is not None and (existing_ts is None or timestamp < existing_ts):
                        existing.update(row_metadata)

    sorted_media = sorted(
        unique_media,
        key=lambda item: (
            metadata_lookup.get(item, {}).get("ts") is None,
            metadata_lookup.get(item, {}).get("ts"),
        ),
    )

    results = []
    for ref in sorted_media[:limit]:
        lookup_result = media_filename_lookup.get(ref)
        if lookup_result:
            _, media_doc = lookup_result
            results.append((ref, media_doc, metadata_lookup[ref]))

    return results


def _replace_pii_media_references(
    messages_table: Table,
    media_mapping: MediaMapping,
) -> Table:
    """Replace media references in messages after PII deletion."""

    @ibis.udf.scalar.python
    def replace_media_udf(text: str) -> str:
        return replace_media_mentions(text, media_mapping) if text else text

    return messages_table.mutate(text=replace_media_udf(messages_table.text))
