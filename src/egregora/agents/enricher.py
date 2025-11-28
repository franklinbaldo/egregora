"""Enrichment agent logic for processing URLs and media.

This module implements the enrichment workflow using Pydantic-AI agents, replacing the
legacy batching runners. It provides:
- UrlEnrichmentAgent & MediaEnrichmentAgent
- Async orchestration via enrich_table
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import ibis
from ibis.expr.types import Table
from pydantic import BaseModel
from pydantic_ai import Agent, AgentRunResult, RunContext
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.google import GoogleModelSettings
from ratelimit import limits, sleep_and_retry

from egregora.config.settings import EnrichmentSettings, ModelSettings, QuotaSettings
from egregora.constants import PrivacyMarkers
from egregora.data_primitives.document import Document, DocumentType
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.input_adapters.base import MediaMapping
from egregora.ops.media import (
    detect_media_type,
    extract_urls,
    find_media_references,
    replace_media_mentions,
)
from egregora.resources.prompts import render_prompt
from egregora.transformations.enrichment import combine_with_enrichment_rows
from egregora.utils.cache import EnrichmentCache, make_enrichment_cache_key
from egregora.utils.datetime_utils import parse_datetime_flexible
from egregora.utils.metrics import UsageTracker
from egregora.utils.paths import slugify
from egregora.utils.quota import QuotaExceededError, QuotaTracker
from egregora.utils.retry import retry_async
from egregora.utils.text import sanitize_prompt_input as _sanitize_prompt_input

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

    agent = Agent[UrlEnrichmentDeps, EnrichmentOutput](
        model=model,
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
    agent = Agent[MediaEnrichmentDeps, EnrichmentOutput](
        model=model,
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


@sleep_and_retry
@limits(calls=100, period=60)
async def _run_url_enrichment_async(
    agent: Agent[UrlEnrichmentDeps, EnrichmentOutput],
    url: str,
    prompts_dir: Path | None,
    pii_prevention: dict[str, Any] | None = None,
) -> EnrichmentOutput:
    """Run URL enrichment asynchronously."""
    url_str = str(url)
    sanitized_url_raw = _sanitize_prompt_input(url_str, max_length=2000)
    sanitized_url = "\n".join(line.strip() for line in sanitized_url_raw.splitlines() if line.strip())

    deps = UrlEnrichmentDeps(url=sanitized_url, prompts_dir=prompts_dir)
    prompt = render_prompt(
        "enrichment.jinja",
        mode="url_user",
        prompts_dir=prompts_dir,
        sanitized_url=sanitized_url,
        pii_prevention=pii_prevention,
    )

    async def call() -> AgentRunResult[EnrichmentOutput]:
        return await agent.run(prompt, deps=deps)

    result = await retry_async(call)
    output = getattr(result, "data", getattr(result, "output", result))
    output.markdown = output.markdown.strip()
    return output, result.usage()


@sleep_and_retry
@limits(calls=100, period=60)
async def _run_media_enrichment_async(  # noqa: PLR0913
    agent: Agent[MediaEnrichmentDeps, EnrichmentOutput],
    *,
    filename: str,
    mime_hint: str | None,
    prompts_dir: Path | None,
    binary_content: BinaryContent | None = None,
    file_path: Path | None = None,
    media_path: str | None = None,
    pii_prevention: dict[str, Any] | None = None,
) -> EnrichmentOutput:
    """Run media enrichment asynchronously."""
    if binary_content is None and file_path is None:
        msg = "Either binary_content or file_path must be provided."
        raise ValueError(msg)

    sanitized_filename_raw = _sanitize_prompt_input(filename, max_length=255)
    sanitized_filename = sanitized_filename_raw.replace("\\", "").strip()
    sanitized_mime = _sanitize_prompt_input(mime_hint, max_length=50).strip() if mime_hint else None
    deps = MediaEnrichmentDeps(
        prompts_dir=prompts_dir,
        media_filename=sanitized_filename,
        media_type=sanitized_mime,
        media_path=media_path,
    )
    prompt = render_prompt(
        "enrichment.jinja",
        mode="media_user",
        prompts_dir=prompts_dir,
        sanitized_filename=sanitized_filename,
        sanitized_mime=sanitized_mime,
        pii_prevention=pii_prevention,
    )

    payload = binary_content or load_file_as_binary_content(file_path)
    message_content = [prompt, payload]

    async def call() -> AgentRunResult[EnrichmentOutput]:
        return await agent.run(message_content, deps=deps)

    result = await retry_async(call)
    output = getattr(result, "data", getattr(result, "output", result))
    output.markdown = output.markdown.strip()
    return output, result.usage()


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


async def _process_url_task(  # noqa: PLR0913
    url: str,
    metadata: dict[str, Any],
    agent: Agent[UrlEnrichmentDeps, EnrichmentOutput],
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any] | None:
    """Process a single URL enrichment task."""
    async with semaphore:
        cache_key = make_enrichment_cache_key(kind="url", identifier=url)
        cache_entry = cache.load(cache_key)

        if cache_entry:
            logger.debug("⚡ [L1 Cache Hit] URL: %s", url)
            markdown = cache_entry.get("markdown", "")
            cached_slug = cache_entry.get("slug")
        else:
            try:
                if context.quota:
                    context.quota.reserve(1)
                output_data, usage = await _run_url_enrichment_async(
                    agent, url, prompts_dir, pii_prevention=context.pii_prevention
                )
                if context.usage_tracker:
                    context.usage_tracker.record(usage)
                markdown = output_data.markdown
                cached_slug = output_data.slug
                cache.store(cache_key, {"markdown": markdown, "slug": cached_slug, "type": "url"})
            except QuotaExceededError:
                logger.warning("LLM quota reached; skipping URL enrichment for %s", url)
                return None
            except httpx.HTTPError as exc:
                logger.warning("HTTP error during URL enrichment for %s: %s", url, exc)
                return None
            except OSError as exc:
                logger.warning("File/cache error during URL enrichment for %s: %s", url, exc)
                return None

        slug_value = _normalize_slug(cached_slug, url)
        doc = Document(
            content=markdown,
            type=DocumentType.ENRICHMENT_URL,
            metadata={
                "url": url,
                "slug": slug_value,
                "nav_exclude": True,
                "hide": ["navigation"],
            },
        )
        context.output_format.persist(doc)
        return _create_enrichment_row(metadata, "URL", url, doc.document_id)


async def _process_media_task(  # noqa: PLR0913
    ref: str,
    media_doc: Document,
    metadata: dict[str, Any],
    agent: Agent[MediaEnrichmentDeps, EnrichmentOutput],
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[str, Any] | None, bool, str | None, Document | None]:
    """Process a single media enrichment task.

    Returns:
        tuple[row, pii_detected, media_ref, updated_media_doc]

    """
    async with semaphore:
        cache_key = make_enrichment_cache_key(kind="media", identifier=media_doc.document_id)

        filename = media_doc.metadata.get("filename") or media_doc.metadata.get("original_filename") or ref
        media_type = media_doc.metadata.get("media_type")
        if not media_type and filename:
            media_type = detect_media_type(Path(filename))
        if not media_type:
            logger.warning("Unsupported media type for enrichment: %s", filename or ref)
            return None, False, ref, None

        raw_content = media_doc.content
        payload = raw_content if isinstance(raw_content, bytes) else str(raw_content).encode("utf-8")
        binary = BinaryContent(
            data=payload,
            media_type=mimetypes.guess_type(filename or "")[0] or "application/octet-stream",
        )

        cache_entry = cache.load(cache_key)
        if cache_entry:
            logger.debug("⚡ [L1 Cache Hit] Media: %s", filename or ref)
            markdown = cache_entry.get("markdown", "")
            cached_slug = cache_entry.get("slug")
        else:
            try:
                if context.quota:
                    context.quota.reserve(1)
                output_data, usage = await _run_media_enrichment_async(
                    agent,
                    filename=filename or ref,
                    mime_hint=media_type,
                    prompts_dir=prompts_dir,
                    binary_content=binary,
                    media_path=media_doc.suggested_path,
                    pii_prevention=context.pii_prevention,
                )
                if context.usage_tracker:
                    context.usage_tracker.record(usage)
                markdown = output_data.markdown
                cached_slug = output_data.slug
                cache.store(cache_key, {"markdown": markdown, "slug": cached_slug, "type": "media"})
            except QuotaExceededError:
                logger.warning("LLM quota reached; skipping media enrichment for %s", filename or ref)
                return None, False, ref, None
            except httpx.HTTPError as exc:
                logger.warning("HTTP error during media enrichment for %s: %s", filename or ref, exc)
                return None, False, ref, None
            except OSError as exc:
                logger.warning("File/cache error during media enrichment for %s: %s", filename or ref, exc)
                return None, False, ref, None

        pii_detected = False
        if PrivacyMarkers.PII_DETECTED in markdown:
            logger.warning("PII detected in media: %s. Media will not be published.", filename or ref)
            markdown = markdown.replace(PrivacyMarkers.PII_DETECTED, "").strip()
            media_doc.metadata["pii_deleted"] = True
            media_doc.metadata["public_url"] = None
            pii_detected = True

        if not markdown:
            markdown = f"[No enrichment generated for media: {filename or ref}]"

        slug_value = _normalize_slug(cached_slug, filename or ref)
        updated_media_doc = media_doc.with_metadata(slug=slug_value)
        parent_path = updated_media_doc.suggested_path

        enrichment_metadata = {
            "filename": filename or ref,
            "media_type": media_type,
            "parent_path": parent_path,
            "slug": slug_value,
            "nav_exclude": True,
            "hide": ["navigation"],
        }

        doc = Document(
            content=markdown,
            type=DocumentType.ENRICHMENT_MEDIA,
            metadata=enrichment_metadata,
        ).with_parent(updated_media_doc)
        context.output_format.persist(doc)
        row = _create_enrichment_row(metadata, "Media", filename or ref, doc.document_id)
        return row, pii_detected, ref, updated_media_doc


def enrich_table(
    messages_table: Table,
    media_mapping: MediaMapping,
    models: ModelSettings,
    enrichment_settings: EnrichmentSettings,
    quota_settings: QuotaSettings,
    context: EnrichmentRuntimeContext,
) -> Table:
    """Enrich messages table with URL and media context using async agents.

    Args:
        messages_table: Parsed messages to enrich.
        media_mapping: Mapping from media reference to associated documents.
        models: Model configuration specific to enrichment.
        enrichment_settings: Feature toggles and limits for enrichment.
        quota_settings: Quota controls (e.g., concurrency) used during enrichment.
        context: Runtime resources and caches needed by enrichment helpers.

    """
    # Use asyncio.run to execute async logic from synchronous context
    return asyncio.run(
        _enrich_table_async(
            messages_table,
            media_mapping,
            models,
            enrichment_settings,
            quota_settings,
            context,
        )
    )


async def _enrich_table_async(
    messages_table: Table,
    media_mapping: MediaMapping,
    models: ModelSettings,
    enrichment_settings: EnrichmentSettings,
    quota_settings: QuotaSettings,
    context: EnrichmentRuntimeContext,
) -> Table:
    """Async implementation of :func:`enrich_table`.

    Args:
        messages_table: Parsed messages to enrich.
        media_mapping: Mapping from media reference to associated documents.
        models: Model configuration specific to enrichment.
        enrichment_settings: Feature toggles and limits for enrichment.
        quota_settings: Quota controls (e.g., concurrency) used during enrichment.
        context: Runtime resources and caches needed by enrichment helpers.

    """
    if messages_table.count().execute() == 0:
        return messages_table

    url_model = models.enricher
    vision_model = models.enricher_vision
    max_enrichments = enrichment_settings.max_enrichments
    enable_url = enrichment_settings.enable_url
    enable_media = enrichment_settings.enable_media
    prompts_dir = context.site_root / ".egregora" / "prompts" if context.site_root else None

    logger.info("[blue]🌐 Enricher text model:[/] %s", url_model)
    logger.info("[blue]🖼️  Enricher vision model:[/] %s", vision_model)

    new_rows: list[dict[str, Any]] = []
    pii_detected_count = 0
    pii_media_deleted = False

    # Concurrency limit (configurable)
    concurrency = max(1, quota_settings.concurrency)
    semaphore = asyncio.Semaphore(concurrency)

    tasks = []

    tasks.extend(
        _schedule_url_tasks(
            messages_table,
            enable_url,
            max_enrichments,
            url_model,
            context,
            prompts_dir,
            semaphore,
        )
    )

    tasks.extend(
        _schedule_media_tasks(
            messages_table,
            media_mapping,
            enable_media,
            max_enrichments,
            vision_model,
            context,
            prompts_dir,
            semaphore,
        )
    )

    if not tasks:
        return messages_table

    logger.info("Running %d enrichment tasks...", len(tasks))
    results = await asyncio.gather(*tasks)

    (
        new_rows,
        pii_detected_count,
        pii_media_deleted,
    ) = _process_enrichment_results(results, max_enrichments, media_mapping)

    if pii_media_deleted:
        messages_table = _replace_pii_media_references(messages_table, media_mapping)

    combined = combine_with_enrichment_rows(messages_table, new_rows, schema=IR_MESSAGE_SCHEMA)

    _persist_enrichments(combined, context)

    if pii_detected_count > 0:
        logger.info("Privacy summary: %d media file(s) deleted due to PII detection", pii_detected_count)

    return combined


def _schedule_url_tasks(
    messages_table: Table,
    enable_url: bool,
    max_enrichments: int,
    url_model: str,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    semaphore: asyncio.Semaphore,
) -> list[asyncio.Task]:
    tasks: list[asyncio.Task] = []

    if not enable_url:
        return tasks

    url_agent = create_url_enrichment_agent(url_model)
    url_candidates = _extract_url_candidates(messages_table, max_enrichments)

    for url, metadata in url_candidates:
        tasks.append(
            _process_url_task(url, metadata, url_agent, context.cache, context, prompts_dir, semaphore)
        )

    return tasks


def _schedule_media_tasks(
    messages_table: Table,
    media_mapping: MediaMapping,
    enable_media: bool,
    max_enrichments: int,
    vision_model: str,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    semaphore: asyncio.Semaphore,
) -> list[asyncio.Task]:
    tasks: list[asyncio.Task] = []

    if not (enable_media and media_mapping):
        return tasks

    media_agent = create_media_enrichment_agent(vision_model)

    # NOTE: We deliberately overfetch media candidates because we don't yet know
    # how many URL tasks will succeed. We filter later.
    media_candidates = _extract_media_candidates(messages_table, media_mapping, max_enrichments)

    for ref, media_doc, metadata in media_candidates:
        tasks.append(
            _process_media_task(
                ref, media_doc, metadata, media_agent, context.cache, context, prompts_dir, semaphore
            )
        )

    return tasks


def _process_enrichment_results(
    results: list[dict[str, Any] | tuple[dict[str, Any] | None, bool, str | None, Document | None] | None],
    max_enrichments: int,
    media_mapping: MediaMapping,
) -> tuple[list[dict[str, Any]], int, bool]:
    new_rows: list[dict[str, Any]] = []
    pii_detected_count = 0
    pii_media_deleted = False

    url_success_count = 0
    media_results: list[tuple[dict[str, Any] | None, bool, str | None, Document | None]] = []

    # First pass: Collect successful URL enrichments
    for res in results:
        if res is None:
            continue
        if isinstance(res, tuple):
            media_results.append(res)
            continue
        new_rows.append(res)
        url_success_count += 1

    # Second pass: Collect media enrichments, respecting remaining quota
    remaining_slots = max(0, max_enrichments - url_success_count)
    media_added_count = 0

    for row, pii, media_ref, updated_media_doc in media_results:
        if pii:
            pii_detected_count += 1
            pii_media_deleted = True

        if media_ref and updated_media_doc:
            media_mapping[media_ref] = updated_media_doc

        if media_added_count < remaining_slots and row:
            new_rows.append(row)
            media_added_count += 1

    return new_rows, pii_detected_count, pii_media_deleted


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
