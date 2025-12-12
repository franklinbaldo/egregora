"""Enrichment agent logic for processing URLs and media.

This module implements the enrichment workflow using Pydantic-AI agents, replacing the
legacy batching runners. It provides:
- UrlEnrichmentAgent & MediaEnrichmentAgent
- Async orchestration via enrich_table
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
import uuid
import zipfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

import ibis
from ibis.common.exceptions import IbisError
from ibis.expr.types import Table
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.google import GoogleModelSettings

from egregora.config.settings import EnrichmentSettings
from egregora.data_primitives.document import Document, DocumentType
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.database.streaming import ensure_deterministic_order, stream_ibis
from egregora.input_adapters.base import MediaMapping
from egregora.models.google_batch import GoogleBatchModel
from egregora.ops.media import extract_urls, find_media_references, replace_media_mentions
from egregora.orchestration.worker_base import BaseWorker
from egregora.resources.prompts import render_prompt
from egregora.utils.cache import EnrichmentCache, make_enrichment_cache_key
from egregora.utils.datetime_utils import parse_datetime_flexible
from egregora.utils.metrics import UsageTracker
from egregora.utils.model_fallback import create_fallback_model
from egregora.utils.paths import slugify
from egregora.utils.quota import QuotaTracker

if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants & Patterns
# ---------------------------------------------------------------------------

_MARKDOWN_LINK_PATTERN = re.compile(r"(?:!\[|\[)[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")
_UUID_PATTERN = re.compile(r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.\w+)")


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


def _normalize_slug(candidate: str | None, identifier: str) -> str:
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
        raise ValueError(msg)

    value = slugify(candidate.strip())
    if not value:
        msg = f"LLM slug '{candidate}' is invalid after normalization for: {identifier[:100]}"
        raise ValueError(msg)

    return value


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


def create_url_enrichment_agent(
    model: str,
) -> Agent[UrlEnrichmentDeps, EnrichmentOutput]:
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
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY or GEMINI_API_KEY required for enrichment"
        raise ValueError(msg)
    model_instance = GoogleBatchModel(api_key=api_key, model_name=model)

    agent = Agent[UrlEnrichmentDeps, EnrichmentOutput](
        model=model_instance,
        output_type=EnrichmentOutput,
        model_settings=model_settings,
    )

    @agent.system_prompt
    def system_prompt(ctx: RunContext[UrlEnrichmentDeps]) -> str:
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


def create_media_enrichment_agent(
    model: str,
) -> Agent[MediaEnrichmentDeps, EnrichmentOutput]:
    """Create media enrichment agent.

    Args:
        model: The model name to use.

    """
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY or GEMINI_API_KEY required for enrichment"
        raise ValueError(msg)
    model_instance = GoogleBatchModel(api_key=api_key, model_name=model)
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


def _safe_timestamp_plus_one(timestamp: datetime | str | Any) -> datetime:
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
        "attrs": {
            "enrichment_type": enrichment_type,
            "enrichment_id": enrichment_id_str,
        },
        "pii_flags": None,
        "created_at": message_metadata.get("created_at"),
        "created_by_run": _uuid_to_str(message_metadata.get("created_by_run")),
    }


def _frame_to_records(frame: Any) -> list[dict[str, Any]]:
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


def _iter_table_batches(table: Table, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
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

    current_run_id = run_id or uuid.uuid4()
    max_enrichments = enrichment_settings.max_enrichments

    url_count = _enqueue_url_enrichments(
        messages_table,
        max_enrichments,
        context,
        current_run_id,
        enable_url=enrichment_settings.enable_url,
    )

    media_config = MediaEnrichmentConfig(
        media_mapping=media_mapping,
        max_enrichments=max_enrichments,
        enable_media=enrichment_settings.enable_media,
    )
    media_count = _enqueue_media_enrichments(
        messages_table,
        context,
        current_run_id,
        media_config,
    )
    logger.info("Scheduled %d URL tasks and %d Media tasks", url_count, media_count)


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


def _enqueue_url_enrichments(
    messages_table: Table,
    max_enrichments: int,
    context: EnrichmentRuntimeContext,
    run_id: uuid.UUID,
    *,
    enable_url: bool,
) -> int:
    if not enable_url or max_enrichments <= 0:
        return 0

    candidates = _extract_url_candidates(messages_table, max_enrichments)
    scheduled = 0
    for url, metadata in candidates:
        cache_key = make_enrichment_cache_key(kind="url", identifier=url)
        if context.cache.load(cache_key) is not None:
            continue

        payload = {
            "type": "url",
            "url": url,
            "message_metadata": _serialize_metadata(metadata),
        }
        context.task_store.enqueue("enrich_url", payload, run_id)
        scheduled += 1
    return scheduled


@dataclass
class MediaEnrichmentConfig:
    """Config for media enrichment enqueueing."""

    media_mapping: MediaMapping
    max_enrichments: int
    enable_media: bool


def _enqueue_media_enrichments(
    messages_table: Table,
    context: EnrichmentRuntimeContext,
    run_id: uuid.UUID,
    config: MediaEnrichmentConfig,
) -> int:
    if not config.enable_media or config.max_enrichments <= 0:
        return 0

    candidates = _extract_media_candidates(messages_table, config.media_mapping, config.max_enrichments)
    scheduled = 0
    for ref, media_doc, metadata in candidates:
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
            "suggested_path": (str(media_doc.suggested_path) if media_doc.suggested_path else None),
            "message_metadata": _serialize_metadata(metadata),
        }
        context.task_store.enqueue("enrich_media", payload, run_id)
        scheduled += 1
        if scheduled >= config.max_enrichments:
            break
    return scheduled


def _serialize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    timestamp = metadata.get("ts")
    created_at = metadata.get("created_at")
    return {
        "ts": timestamp.isoformat() if timestamp else None,
        "tenant_id": metadata.get("tenant_id"),
        "source": metadata.get("source"),
        "thread_id": _uuid_to_str(metadata.get("thread_id")),
        "author_uuid": _uuid_to_str(metadata.get("author_uuid")),
        "created_at": (created_at.isoformat() if hasattr(created_at, "isoformat") else created_at),
        "created_by_run": _uuid_to_str(metadata.get("created_by_run")),
    }


def _process_url_row(
    row: dict[str, Any],
    url_metadata: dict[str, dict[str, Any]],
    discovered_count: int,
    max_enrichments: int,
) -> int:
    """Process a single row for URL extraction."""
    message = row.get("text")
    if not message:
        return discovered_count
    urls = extract_urls(message)
    if not urls:
        return discovered_count

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
                return discovered_count
        else:
            # Keep earliest timestamp
            existing_ts = existing.get("ts")
            if timestamp is not None and (existing_ts is None or timestamp < existing_ts):
                existing.update(row_metadata)
    return discovered_count


def _extract_url_candidates(messages_table: Table, max_enrichments: int) -> list[tuple[str, dict[str, Any]]]:
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
            discovered_count = _process_url_row(row, url_metadata, discovered_count, max_enrichments)

        if discovered_count >= max_enrichments:
            break

    sorted_items = sorted(
        url_metadata.items(),
        key=lambda item: (item[1]["ts"] is None, item[1]["ts"]),
    )
    return sorted_items[:max_enrichments]


def _process_media_row(
    row: dict[str, Any],
    media_filename_lookup: dict[str, tuple[str, Document]],
    metadata_lookup: dict[str, dict[str, Any]],
    unique_media: set[str],
) -> None:
    """Process a single row for media extraction."""
    message = row.get("text")
    if not message:
        return

    refs = find_media_references(message)
    refs.extend(_MARKDOWN_LINK_PATTERN.findall(message))
    refs.extend(_UUID_PATTERN.findall(message))

    if not refs:
        return

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


def _extract_media_candidates(
    messages_table: Table, media_mapping: MediaMapping, limit: int
) -> list[tuple[str, Document, dict[str, Any]]]:
    """Extract unique Media candidates with metadata.

    This function scans messages for media references and queues them for enrichment.
    It does NOT validate existence or load content at this stage - that happens
    during the enrichment task execution (lazy loading).
    """
    if limit <= 0:
        return []

    # Note: media_mapping is passed but ignored to avoid pre-extraction overhead.
    # Validation happens lazily in the enricher worker.

    unique_media: set[str] = set()
    metadata_lookup: dict[str, dict[str, Any]] = {}

    # We still need to construct pseudo-Documents to maintain the return signature
    # until we can refactor the return type.
    document_lookup: dict[str, Document] = {}

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
            if len(unique_media) >= limit:
                break

            message = row.get("text")
            if not message:
                continue

            refs = find_media_references(message)
            refs.extend(_MARKDOWN_LINK_PATTERN.findall(message))
            # Detect UUID patterns if they are used as references
            uuid_refs = _UUID_PATTERN.findall(message)
            # Filter UUIDs to avoid false positives (simple heuristic)
            refs.extend([u for u in uuid_refs if "media" in str(row)])

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
                # Simple deduplication by reference string
                if ref in unique_media:
                    # Update metadata with earliest timestamp if needed
                    existing = metadata_lookup.get(ref)
                    if existing:
                        existing_ts = existing.get("ts")
                        if existing_ts and timestamp and timestamp < existing_ts:
                            existing.update(row_metadata)
                    continue

                # New candidate found
                unique_media.add(ref)
                metadata_lookup[ref] = row_metadata.copy()

                # Create a placeholder Document
                # We use the ref as the filename since we haven't resolved it yet
                # The ID is deterministic based on the ref
                doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, ref))
                document_lookup[ref] = Document(
                    content=b"",  # Empty content for placeholder
                    type=DocumentType.MEDIA,
                    id=doc_id,  # Deterministic ID
                    metadata={
                        "filename": ref,
                        "original_filename": ref,
                        "media_type": mimetypes.guess_type(ref)[0] or "application/octet-stream",
                    },
                )

        if len(unique_media) >= limit:
            break

    # Sort by timestamp
    sorted_refs = sorted(
        unique_media, key=lambda r: (metadata_lookup[r]["ts"] is None, metadata_lookup[r]["ts"])
    )

    return [(ref, document_lookup[ref], metadata_lookup[ref]) for ref in sorted_refs[:limit]]


def _replace_pii_media_references(
    messages_table: Table,
    media_mapping: MediaMapping,
) -> Table:
    """Replace media references in messages after PII deletion."""

    @ibis.udf.scalar.python
    def replace_media_udf(text: str) -> str:
        return replace_media_mentions(text, media_mapping) if text else text

    return messages_table.mutate(text=replace_media_udf(messages_table.text))


class EnrichmentWorker(BaseWorker):
    """Worker for media enrichment (e.g. image description)."""

    def __init__(self, ctx: PipelineContext | EnrichmentRuntimeContext):
        super().__init__(ctx)
        self.zip_handle: zipfile.ZipFile | None = None
        self.media_index: dict[str, str] = {}

        if self.ctx.input_path and self.ctx.input_path.exists() and self.ctx.input_path.is_file():
            try:
                self.zip_handle = zipfile.ZipFile(self.ctx.input_path, "r")
                # Build index for O(1) lookup
                for info in self.zip_handle.infolist():
                    if not info.is_dir():
                        self.media_index[Path(info.filename).name.lower()] = info.filename
            except Exception:
                logger.warning("Failed to open source ZIP %s", self.ctx.input_path)

    def close(self) -> None:
        """Explicitly close the ZIP handle to release resources.

        Should be called when done with the worker. Also called by __exit__
        for context manager support.
        """
        if self.zip_handle:
            try:
                self.zip_handle.close()
            except OSError:
                logger.debug("Error closing ZIP handle", exc_info=True)
            finally:
                self.zip_handle = None
                self.media_index = {}

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - ensures ZIP handle is closed."""
        self.close()

    def run(self) -> int:
        """Process pending enrichment tasks in batches."""
        # Configurable batch size
        batch_size = 50
        tasks = self.task_store.fetch_pending(task_type="enrich_url", limit=batch_size)
        media_tasks = self.task_store.fetch_pending(task_type="enrich_media", limit=batch_size)

        total_tasks = len(tasks) + len(media_tasks)
        if not total_tasks:
            return 0

        logger.info(
            "[Enrichment] Processing %d tasks (URL: %d, Media: %d)", total_tasks, len(tasks), len(media_tasks)
        )

        processed_count = 0

        if tasks:
            count = self._process_url_batch(tasks)
            processed_count += count
            logger.info("[Enrichment] URL batch complete: %d/%d", count, len(tasks))

        if media_tasks:
            count = self._process_media_batch(media_tasks)
            processed_count += count
            logger.info("[Enrichment] Media batch complete: %d/%d", count, len(media_tasks))

        logger.info("Enrichment complete: %d/%d tasks processed", processed_count, total_tasks)
        return processed_count

    def _process_url_batch(self, tasks: list[dict[str, Any]]) -> int:
        tasks_data = self._prepare_url_tasks(tasks)
        if not tasks_data:
            return 0

        max_concurrent = self._determine_concurrency(len(tasks_data))
        results = self._execute_url_enrichments(tasks_data, max_concurrent)
        return self._persist_url_results(results)

    def _enrich_single_url(self, task_data: dict) -> tuple[dict, EnrichmentOutput | None, str | None]:
        """Enrich a single URL with fallback support (sync wrapper)."""
        task = task_data["task"]
        url = task_data["url"]
        prompt = task_data["prompt"]

        try:
            # Create agent with fallback
            model = create_fallback_model(self.ctx.config.models.enricher)
            agent = Agent(model=model, output_type=EnrichmentOutput)

            # Use run_sync to execute the async agent synchronously
            result = agent.run_sync(prompt)
        except Exception as e:
            logger.exception("Failed to enrich URL %s", url)
            return task, None, str(e)
        else:
            return task, result.output, None

    def _prepare_url_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Parse payloads and render prompts for URL enrichment tasks."""
        tasks_data: list[dict[str, Any]] = []
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None

        for task in tasks:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                task["_parsed_payload"] = payload

                url = payload["url"]
                prompt = render_prompt(
                    "enrichment.jinja",
                    mode="url_user",
                    prompts_dir=prompts_dir,
                    sanitized_url=url,
                ).strip()

                tasks_data.append({"task": task, "url": url, "prompt": prompt})
            except Exception as exc:
                logger.exception("Failed to prepare URL task %s", task["task_id"])
                self.task_store.mark_failed(task["task_id"], f"Preparation failed: {exc!s}")

        return tasks_data

    def _determine_concurrency(self, task_count: int) -> int:
        enrichment_concurrency = getattr(self.ctx.config.enrichment, "max_concurrent_enrichments", 5)
        global_concurrency = getattr(self.ctx.config.quota, "concurrency", 1)
        max_concurrent = min(enrichment_concurrency, global_concurrency)

        logger.info(
            "Processing %d enrichment tasks with max concurrency of %d (enrichment limit: %d, global limit: %d)",
            task_count,
            max_concurrent,
            enrichment_concurrency,
            global_concurrency,
        )

        return max_concurrent

    def _execute_url_enrichments(
        self, tasks_data: list[dict[str, Any]], max_concurrent: int
    ) -> list[tuple[dict, EnrichmentOutput | None, str | None]]:
        results: list[tuple[dict, EnrichmentOutput | None, str | None]] = []
        total = len(tasks_data)
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_task = {executor.submit(self._enrich_single_url, td): td for td in tasks_data}
            for i, future in enumerate(as_completed(future_to_task), 1):
                try:
                    results.append(future.result())
                    logger.info("[Enrichment] URL task %d/%d complete", i, total)
                except Exception as exc:
                    task = future_to_task[future]["task"]
                    logger.exception("Enrichment failed for %s", task["task_id"])
                    results.append((task, None, str(exc)))

        return results

    def _persist_url_results(self, results: list[tuple[dict, EnrichmentOutput | None, str | None]]) -> int:
        new_rows = []
        for task, output, error in results:
            if error:
                self.task_store.mark_failed(task["task_id"], error)
                continue

            if not output:
                continue

            try:
                payload = task["_parsed_payload"]
                url = payload["url"]
                slug_value = _normalize_slug(output.slug, url)

                doc = Document(
                    content=output.markdown,
                    type=DocumentType.ENRICHMENT_URL,
                    metadata={
                        "url": url,
                        "slug": slug_value,
                        "nav_exclude": True,
                        "hide": ["navigation"],
                    },
                    id=slug_value,  # Semantic ID
                )

                # V3 Architecture: Use ContentLibrary if available
                if self.ctx.library:
                    self.ctx.library.save(doc)
                else:
                    self.ctx.output_format.persist(doc)

                metadata = payload["message_metadata"]
                row = _create_enrichment_row(metadata, "URL", url, doc.document_id)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])
            except Exception as exc:
                logger.exception("Failed to persist enrichment for %s", task["task_id"])
                self.task_store.mark_failed(task["task_id"], f"Persistence error: {exc!s}")

        if new_rows:
            try:
                self.ctx.storage.ibis_conn.insert("messages", new_rows)
                logger.info("Inserted %d enrichment rows", len(new_rows))
            except Exception:
                logger.exception("Failed to insert enrichment rows")

        return len(results)

    def _process_media_batch(self, tasks: list[dict[str, Any]]) -> int:
        requests, task_map = self._prepare_media_requests(tasks)
        if not requests:
            return 0

        results = self._execute_media_batch(requests, task_map)
        return self._persist_media_results(results, task_map)

    def _extract_text(self, response: dict[str, Any] | None) -> str:
        if not response:
            return ""
        if "text" in response:
            return response["text"]
        texts = []
        for cand in response.get("candidates") or []:
            content = cand.get("content") or {}
            texts.extend(part["text"] for part in content.get("parts") or [] if "text" in part)
        return "\n".join(texts)

    def _prepare_media_requests(
        self, tasks: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None
        requests: list[dict[str, Any]] = []
        task_map: dict[str, dict[str, Any]] = {}

        for task in tasks:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                task["_parsed_payload"] = payload

                file_bytes = self._load_media_bytes(task, payload)
                if file_bytes is None:
                    continue

                filename = payload["filename"]
                media_type = payload["media_type"]
                b64_data = base64.b64encode(file_bytes).decode("utf-8")

                prompt = render_prompt(
                    "enrichment.jinja",
                    mode="media_user",
                    prompts_dir=prompts_dir,
                    sanitized_filename=filename,
                    sanitized_mime=media_type,
                ).strip()

                tag = str(task["task_id"])
                requests.append(
                    {
                        "tag": tag,
                        "contents": [
                            {
                                "parts": [
                                    {"text": prompt},
                                    {
                                        "inlineData": {
                                            "mimeType": media_type,
                                            "data": b64_data,
                                        }
                                    },
                                ]
                            }
                        ],
                        "config": {"response_modalities": ["TEXT"]},
                    }
                )
                task_map[tag] = task

            except Exception as exc:
                logger.exception("Failed to prepare media task %s", task.get("task_id"))
                self.task_store.mark_failed(task.get("task_id"), str(exc))

        return requests, task_map

    def _load_media_bytes(self, task: dict[str, Any], payload: dict[str, Any]) -> bytes | None:
        """Load media bytes directly from source ZIP file via index."""
        original_filename = payload.get("original_filename") or payload.get("filename")
        if not original_filename:
            logger.warning("No filename in media task %s", task["task_id"])
            self.task_store.mark_failed(task["task_id"], "No filename in task payload")
            return None

        zf = self.zip_handle
        media_index = self.media_index
        should_close = False

        # Fallback initialization if ZIP wasn't opened in __init__
        if zf is None:
            input_path = self.ctx.input_path
            if not input_path or not input_path.exists():
                logger.warning("Input path not available for media task %s", task["task_id"])
                self.task_store.mark_failed(task["task_id"], "Input path not available")
                return None
            try:
                zf = zipfile.ZipFile(input_path, "r")
                should_close = True
                # Build index on the fly
                media_index = {}
                for info in zf.infolist():
                    if not info.is_dir():
                        media_index[Path(info.filename).name.lower()] = info.filename
            except Exception as exc:
                logger.warning("Failed to open source ZIP %s: %s", input_path, exc)
                self.task_store.mark_failed(task["task_id"], f"Failed to open ZIP: {exc}")
                return None

        try:
            target_lower = original_filename.lower()
            full_path = media_index.get(target_lower)

            if full_path:
                media_bytes = zf.read(full_path)
                logger.debug("Loaded %d bytes from %s", len(media_bytes), full_path)
                return media_bytes

            logger.warning("Media file %s not found in ZIP for task %s", original_filename, task["task_id"])
            self.task_store.mark_failed(task["task_id"], f"Media file not found: {original_filename}")
            return None

        except (OSError, zipfile.BadZipFile) as exc:
            logger.warning("Failed to read media from ZIP for task %s: %s", task["task_id"], exc)
            self.task_store.mark_failed(task["task_id"], f"Failed to read ZIP: {exc}")
            return None
        finally:
            if should_close and zf:
                zf.close()

    def _execute_media_batch(
        self, requests: list[dict[str, Any]], task_map: dict[str, dict[str, Any]]
    ) -> list[Any]:
        model_name = self.ctx.config.models.enricher_vision
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            msg = "GOOGLE_API_KEY or GEMINI_API_KEY required for media enrichment"
            raise ValueError(msg)

        # Check if batch_images is enabled (all images in one call)
        batch_images = getattr(self.ctx.config.enrichment, "batch_images", True)
        if batch_images and len(requests) > 1:
            try:
                logger.info("[MediaEnricher] Using single-call batch mode for %d images", len(requests))
                return self._execute_media_single_call(requests, task_map, model_name, api_key)
            except Exception as single_call_exc:
                logger.warning(
                    "[MediaEnricher] Single-call batch failed (%s), falling back to standard batch",
                    single_call_exc,
                )

        # Standard batch API (one request per image)
        model = GoogleBatchModel(api_key=api_key, model_name=model_name)
        try:
            return asyncio.run(model.run_batch(requests))
        except Exception as batch_exc:
            # Batch failed (likely quota exceeded) - fallback to individual calls
            logger.warning(
                "Batch API failed (%s), falling back to individual calls for %d requests",
                batch_exc,
                len(requests),
            )
            return self._execute_media_individual(requests, task_map, model_name, api_key)

    def _execute_media_single_call(
        self,
        requests: list[dict[str, Any]],
        task_map: dict[str, dict[str, Any]],
        model_name: str,
        api_key: str,
    ) -> list[Any]:
        """Execute all media enrichments in a single API call using Gemini's large context.

        Sends all images together with a combined prompt asking for JSON dict with
        results keyed by filename. This reduces 12 API calls to 1.
        """
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Build combined prompt with all images
        parts: list[dict[str, Any]] = []

        # Extract filenames and build prompt
        filenames = []
        for req in requests:
            tag = req.get("tag")
            task = task_map.get(tag, {})
            payload = task.get("_parsed_payload", {})
            filename = payload.get("filename", tag)
            filenames.append(filename)

            # Add each image's inline data from the request
            contents = req.get("contents", [])
            for content in contents:
                for part in content.get("parts", []):
                    if "inlineData" in part:
                        parts.append({"inlineData": part["inlineData"]})

        # Render prompt from Jinja template
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None
        combined_prompt = render_prompt(
            "enrichment.jinja",
            mode="media_batch",
            prompts_dir=prompts_dir,
            image_count=len(filenames),
            filenames_json=json.dumps(filenames),
            pii_prevention=getattr(self.ctx.config.privacy, "pii_prevention", None),
        ).strip()

        # Build the request: prompt first, then all images
        request_parts = [{"text": combined_prompt}] + parts

        # Make single API call
        response = client.models.generate_content(
            model=model_name,
            contents=[{"parts": request_parts}],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        # Parse JSON response
        response_text = response.text if response.text else ""
        logger.debug("[MediaEnricher] Single-call response: %s", response_text[:500])

        try:
            results_dict = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning("[MediaEnricher] Failed to parse JSON response: %s", e)
            raise ValueError(f"Failed to parse batch response: {e}") from e

        # Convert to BatchResult-like objects
        results = []
        for req in requests:
            tag = req.get("tag")
            task = task_map.get(tag, {})
            payload = task.get("_parsed_payload", {})
            filename = payload.get("filename", tag)

            # Get enrichment data for this filename
            enrichment = results_dict.get(filename, {})
            if enrichment:
                # Build response in expected format
                response_data = {
                    "text": json.dumps(
                        {
                            "slug": enrichment.get("slug", ""),
                            "description": enrichment.get("description", ""),
                            "alt_text": enrichment.get("alt_text", ""),
                            "filename": filename,
                        }
                    )
                }
                result = type(
                    "BatchResult",
                    (),
                    {"tag": tag, "response": response_data, "error": None},
                )()
            else:
                result = type(
                    "BatchResult",
                    (),
                    {"tag": tag, "response": None, "error": {"message": f"No result for {filename}"}},
                )()
            results.append(result)
            logger.info("[MediaEnricher] Processed %s via single-call batch", filename)

        logger.info("[MediaEnricher] Single-call batch complete: %d/%d", len(results), len(requests))
        return results

    def _execute_media_individual(
        self,
        requests: list[dict[str, Any]],
        task_map: dict[str, dict[str, Any]],
        model_name: str,
        api_key: str,
    ) -> list[Any]:
        """Execute media enrichment requests individually (fallback when batch fails)."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        results = []

        for req in requests:
            tag = req.get("tag")
            task = task_map.get(tag)
            if not task:
                continue

            try:
                # Build the request content
                contents = req.get("contents", [])
                config = req.get("config", {})

                # Call Gemini API directly
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(**config) if config else None,
                )

                # Create BatchResult-like object
                result = type(
                    "BatchResult",
                    (),
                    {
                        "tag": tag,
                        "response": {"text": response.text} if response.text else None,
                        "error": None,
                    },
                )()
                results.append(result)
                logger.info("[MediaEnricher] Processed %s via individual call", tag)

            except Exception as exc:
                logger.warning("[MediaEnricher] Individual call failed for %s: %s", tag, exc)
                result = type(
                    "BatchResult",
                    (),
                    {
                        "tag": tag,
                        "response": None,
                        "error": {"message": str(exc)},
                    },
                )()
                results.append(result)

        return results

    def _persist_media_results(self, results: list[Any], task_map: dict[str, dict[str, Any]]) -> int:
        new_rows = []
        for res in results:
            task = task_map.get(res.tag)
            if not task:
                continue

            if res.error:
                self.task_store.mark_failed(task["task_id"], str(res.error))
                continue

            task_result = self._parse_media_result(res, task)
            if task_result is None:
                continue

            payload, slug_value, markdown = task_result
            filename = payload["filename"]
            media_type = payload["media_type"]
            media_id = payload.get("media_id")

            # Load actual media content (was not persisted earlier)
            media_bytes = self._load_media_bytes(task, payload)
            if not media_bytes:
                logger.warning("Could not load media bytes for persistence: %s", filename)
                self.task_store.mark_failed(task["task_id"], "Failed to load media bytes for persistence")
                continue

            # Create media document with slug-based metadata
            media_metadata = {
                "original_filename": payload.get("original_filename"),
                "filename": f"{slug_value}{Path(filename).suffix}",  # Use slug for filename
                "media_type": media_type,
                "slug": slug_value,
                "nav_exclude": True,
                "hide": ["navigation"],
            }

            # Persist the actual media file
            media_doc = Document(
                content=media_bytes,
                type=DocumentType.MEDIA,
                metadata=media_metadata,
                id=media_id if media_id else str(uuid.uuid4()),
                parent_id=media_id,  # Link to original placeholder ID if exists
            )

            try:
                if self.ctx.library:
                    self.ctx.library.save(media_doc)
                else:
                    self.ctx.output_format.persist(media_doc)
                logger.info("Persisted enriched media: %s -> %s", filename, media_doc.metadata["filename"])
            except Exception as exc:
                logger.exception("Failed to persist media file %s", filename)
                self.task_store.mark_failed(task["task_id"], f"Persistence failed: {exc}")
                continue

            # Create and persist the enrichment text document (description)
            enrichment_metadata = {
                "filename": filename,
                "media_type": media_type,
                "parent_path": payload.get("suggested_path"),
                "slug": slug_value,
                "nav_exclude": True,
                "hide": ["navigation"],
            }

            doc = Document(
                content=markdown,
                type=DocumentType.ENRICHMENT_MEDIA,
                metadata=enrichment_metadata,
                id=slug_value,
                parent_id=slug_value,
            )

            if self.ctx.library:
                self.ctx.library.save(doc)
            else:
                self.ctx.output_format.persist(doc)

            metadata = payload["message_metadata"]
            row = _create_enrichment_row(metadata, "Media", filename, doc.document_id)
            if row:
                new_rows.append(row)

            # Update original references in messages table
            original_ref = payload.get("original_filename")
            if original_ref:
                # Determine relative path for replacement (e.g. media/images/slug.jpg)
                # We use the path relative to site root, which works for most SSGs if configured right
                # or we might need to be smarter about relative paths.
                # MKDocs usually resolves from the current page, so 'media/' works if at root,
                # but posts are in 'posts/'. So we might need '../media/' or absolute '/media/'.
                # Let's use the standard "media/" and assume site configuration handles it
                # or use absolute path "/media/..."

                # Determine subfolder based on media_type
                media_subdir = "files"
                if media_type and media_type.startswith("image"):
                    media_subdir = "images"
                elif media_type and media_type.startswith("video"):
                    media_subdir = "videos"
                elif media_type and media_type.startswith("audio"):
                    media_subdir = "audio"

                new_path = f"media/{media_subdir}/{slug_value}{Path(filename).suffix}"

                # Using SQL replace to update all occurrences
                try:
                    # We need to use valid SQL string escaping
                    safe_original = original_ref.replace("'", "''")
                    safe_new = new_path.replace("'", "''")

                    # Update text column
                    # Note: This updates ALL messages containing this ref.
                    # Given filenames are usually unique (timestamps), this is safe.
                    query = f"UPDATE messages SET text = replace(text, '{safe_original}', '{safe_new}') WHERE text LIKE '%{safe_original}%'"
                    self.ctx.storage._conn.execute(query)
                except Exception:
                    logger.warning("Failed to update message references for %s", original_ref)

            self.task_store.mark_completed(task["task_id"])

        if new_rows:
            try:
                self.ctx.storage.ibis_conn.insert("messages", new_rows)
                logger.info("Inserted %d media enrichment rows", len(new_rows))
            except Exception:
                logger.exception("Failed to insert media enrichment rows")

        return len(results)

    def _parse_media_result(self, res: Any, task: dict[str, Any]) -> tuple[dict[str, Any], str, str] | None:
        text = self._extract_text(res.response)
        try:
            clean_text = text.strip()
            clean_text = clean_text.removeprefix("```json")
            clean_text = clean_text.removeprefix("```")
            clean_text = clean_text.removesuffix("```")

            data = json.loads(clean_text.strip())
            slug = data.get("slug")
            markdown = data.get("markdown")

            if not slug or not markdown:
                self.task_store.mark_failed(task["task_id"], "Missing slug or markdown")
                return None

            payload = task["_parsed_payload"]
            slug_value = _normalize_slug(slug, payload["filename"])
        except Exception as exc:
            logger.exception("Failed to parse media result %s", task["task_id"])
            self.task_store.mark_failed(task["task_id"], f"Parse error: {exc!s}")
            return None
        else:
            return payload, slug_value, markdown
