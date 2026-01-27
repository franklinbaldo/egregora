"""Enrichment agent logic for processing URLs and media.

This module implements the enrichment workflow using Pydantic-AI agents. It provides:
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
import shutil
import tempfile
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast

import duckdb
import httpx
import ibis
from google.api_core import exceptions as google_exceptions
from ibis.common.exceptions import IbisError
from pydantic import BaseModel

# WebFetchTool is the client-side fetcher suitable for pydantic-ai
from pydantic_ai import Agent, RunContext, WebFetchTool
# Note: UrlContextTool is deprecated in newer versions, but we keep it for compatibility with the current stack.
# We will migrate to WebFetchTool in a future sprint.
from pydantic_ai import Agent, RunContext, UrlContextTool
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import BinaryContent

from egregora.agents.exceptions import (
    EnrichmentExecutionError,
    EnrichmentFileError,
    EnrichmentParsingError,
    EnrichmentSlugError,
    JinaFetchError,
    MediaStagingError,
)
from egregora.config.settings import EnrichmentSettings
from egregora.data_primitives.datetime_utils import ensure_datetime
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.text import slugify
from egregora.database.message_repository import MessageRepository
from egregora.database.streaming import ensure_deterministic_order, stream_ibis
from egregora.llm.api_keys import get_google_api_key
from egregora.llm.providers.google_batch import GoogleBatchModel
from egregora.orchestration.cache import EnrichmentCache, make_enrichment_cache_key
from egregora.orchestration.exceptions import CacheKeyNotFoundError
from egregora.orchestration.worker_base import BaseWorker
from egregora.resources.prompts import render_prompt
from egregora.security.zip import validate_zip_contents

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import TracebackType

    from ibis.backends.duckdb import Backend as DuckDBBackend
    from ibis.expr.types import Table

    from egregora.input_adapters.base import MediaMapping
    from egregora.llm.usage import UsageTracker
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants & Patterns
# ---------------------------------------------------------------------------

# TODO: [Taskmaster] Externalize hardcoded configuration values
HEARTBEAT_INTERVAL = 10  # Seconds for heartbeat logging

_MARKDOWN_LINK_PATTERN = re.compile(r"(?:!\[|\[)[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")
_UUID_PATTERN = re.compile(r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.\w+)")


# ---------------------------------------------------------------------------
# Shared Models & Helpers
# ---------------------------------------------------------------------------


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
        raise EnrichmentSlugError(msg)

    value = slugify(candidate.strip())
    if not value or value == "post":
        msg = f"LLM slug '{candidate}' is invalid after normalization for: {identifier[:100]}"
        raise EnrichmentSlugError(msg)

    return value


class EnrichmentOutput(BaseModel):
    """Structured output for enrichment agents."""

    slug: str
    markdown: str
    title: str | None = None
    tags: list[str] = []


# ---------------------------------------------------------------------------
# Dependencies & Contexts
# ---------------------------------------------------------------------------


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


@dataclass(frozen=True, slots=True)
class EnrichmentRuntimeContext:
    """Runtime context for enrichment execution."""

    cache: EnrichmentCache
    output_sink: Any
    site_root: Path | None = None
    duckdb_connection: DuckDBBackend | None = None
    target_table: str | None = None
    usage_tracker: UsageTracker | None = None
    pii_prevention: dict[str, Any] | None = None  # LLM-native PII prevention settings
    task_store: Any | None = None  # Added for job queue scheduling


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
    media_identifier: str | None = None,
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
        "media_url": media_identifier,
        "media_type": enrichment_type,
        "attrs": {
            "enrichment_type": enrichment_type,
            "enrichment_id": enrichment_id_str,
        },
        "pii_flags": None,
        "created_at": message_metadata.get("created_at"),
        "created_by_run": _uuid_to_str(message_metadata.get("created_by_run")),
    }


# TODO: [Taskmaster] Refactor brittle data conversion logic
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


# TODO: [Taskmaster] Refactor duplicated enrichment check logic
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

    backend = context.duckdb_connection or messages_table._find_backend(use_default=True)
    repo = MessageRepository(backend)
    candidates = repo.get_url_enrichment_candidates(messages_table, max_enrichments)

    # Pre-check database for already enriched URLs to avoid redundant tasks
    urls_to_check = [c[0] for c in candidates]
    existing_urls: set[str] = set()
    if urls_to_check:
        try:
            # Check for existing URL enrichments in the messages table
            # We look for rows with media_type='URL' and matching media_url
            db_existing = (
                messages_table.filter(
                    (messages_table.media_type == "URL") & (messages_table.media_url.isin(urls_to_check))
                )
                .select("media_url")
                .execute()
            )
            existing_urls = set(db_existing["media_url"].tolist())
        except (IbisError, ValueError) as exc:
            logger.warning(
                "Failed to check database for existing URL enrichments; falling back to cache only: %s",
                exc,
            )

    scheduled = 0
    for url, metadata in candidates:
        # Skip if already in database OR disk cache
        if url in existing_urls:
            continue

        cache_key = make_enrichment_cache_key(kind="url", identifier=url)
        try:
            context.cache.load(cache_key)
            continue
        except CacheKeyNotFoundError:
            pass

        payload = {
            "type": "url",
            "url": url,
            "message_metadata": _serialize_metadata(metadata),
        }
        if context.task_store:
            context.task_store.enqueue("enrich_url", payload)
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

    backend = context.duckdb_connection or messages_table._find_backend(use_default=True)
    repo = MessageRepository(backend)
    candidates = repo.get_media_enrichment_candidates(
        messages_table, config.media_mapping, config.max_enrichments
    )

    # Pre-check database for already enriched media to avoid redundant tasks
    media_ids_to_check = [c[1].document_id for c in candidates]
    existing_media: set[str] = set()
    if media_ids_to_check:
        try:
            # Check for existing Media enrichments in the messages table
            # We look for rows with media_type='Media' and matching media_url (which stores the media_id)
            db_existing = (
                messages_table.filter(
                    (messages_table.media_type == "Media")
                    & (messages_table.media_url.isin(media_ids_to_check))
                )
                .select("media_url")
                .execute()
            )
            existing_media = set(db_existing["media_url"].tolist())
        except (IbisError, ValueError) as exc:
            logger.warning(
                "Failed to check database for existing Media enrichments; falling back to cache only: %s",
                exc,
            )

    scheduled = 0
    for ref, media_doc, metadata in candidates:
        # Skip if already in database OR disk cache
        if media_doc.document_id in existing_media:
            continue

        cache_key = make_enrichment_cache_key(kind="media", identifier=media_doc.document_id)
        try:
            context.cache.load(cache_key)
            continue
        except CacheKeyNotFoundError:
            pass

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
        if context.task_store:
            context.task_store.enqueue("enrich_media", payload)
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
        "created_at": (
            created_at.isoformat() if created_at and hasattr(created_at, "isoformat") else created_at
        ),
        "created_by_run": _uuid_to_str(metadata.get("created_by_run")),
    }


# TODO: [Taskmaster] Decompose monolithic EnrichmentWorker class
class EnrichmentWorker(BaseWorker):
    """Worker for media enrichment (e.g. image description)."""

    def __init__(
        self,
        ctx: PipelineContext,
        enrichment_config: EnrichmentSettings | None = None,
    ) -> None:
        super().__init__(ctx)
        self.ctx: PipelineContext = ctx
        self._enrichment_config_override = enrichment_config
        self.zip_handle: zipfile.ZipFile | None = None
        self.media_index: dict[str, str] = {}
        # Main Architecture: Ephemeral media staging
        self.staging_dir = tempfile.TemporaryDirectory(prefix="egregora_staging_")
        self.staged_files: set[str] = set()

        if self.ctx.input_path and self.ctx.input_path.exists() and self.ctx.input_path.is_file():
            try:
                self.zip_handle = zipfile.ZipFile(self.ctx.input_path, "r")
                validate_zip_contents(self.zip_handle)
                # Build index for O(1) lookup
                for info in self.zip_handle.infolist():
                    if not info.is_dir():
                        self.media_index[Path(info.filename).name.lower()] = info.filename
            except (OSError, zipfile.BadZipFile) as exc:
                logger.warning("Failed to open source ZIP %s: %s", self.ctx.input_path, exc)
                if self.zip_handle:
                    self.zip_handle.close()
                    self.zip_handle = None

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

        # Clean up staging directory (Story 1: Ephemeral media staging)
        if self.staging_dir:
            try:
                self.staging_dir.cleanup()
            except OSError:
                logger.debug("Error cleaning up staging directory", exc_info=True)
            finally:
                self.staging_dir = None
                self.staged_files = set()

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - ensures ZIP handle is closed."""
        self.close()

    def run(self) -> int:
        """Process pending enrichment tasks in batches."""
        if not self.enrichment_config.enabled:
            logger.info("Enrichment is disabled. Skipping enrichment worker.")
            return 0
        # Determine concurrency to scale fetch limit
        # We assume typical batch size of 50.
        base_batch_size = 50
        # We pass a dummy count to _determine_concurrency just to check key/config state
        concurrency = self._determine_concurrency(base_batch_size)

        # Scale fetch limit by concurrency to allow parallel processing of multiple batches
        fetch_limit = base_batch_size * concurrency

        tasks = self.task_store.fetch_pending(task_type="enrich_url", limit=fetch_limit)
        media_tasks = self.task_store.fetch_pending(task_type="enrich_media", limit=fetch_limit)

        total_tasks = len(tasks) + len(media_tasks)
        if not total_tasks:
            return 0

        logger.info(
            "[Enrichment] Processing %d tasks (URL: %d, Media: %d) with concurrency %d",
            total_tasks,
            len(tasks),
            len(media_tasks),
            concurrency,
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

    # TODO: [Taskmaster] Simplify complex async-in-sync wrapper
    def _enrich_single_url(self, task_data: dict) -> tuple[dict, EnrichmentOutput | None, str | None]:
        """Enrich a single URL with fallback support (sync wrapper)."""
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        task = task_data["task"]
        url = task_data["url"]
        prompt = task_data["prompt"]

        try:
            # Create agent with fallback
            model_name = self.ctx.config.models.enricher
            provider = GoogleProvider(api_key=get_google_api_key())
            model = GoogleModel(
                model_name.removeprefix("google-gla:"),
                provider=provider,
            )

            # REGISTER TOOLS:
            # 1. WebFetchTool: Standard client-side fetcher (primary) - passed via builtin_tools
            # 2. fetch_url_with_jina: Fallback service for difficult pages - passed via tools
            agent = Agent(
                model=model,
                output_type=EnrichmentOutput,
                builtin_tools=[WebFetchTool()],  # Built-in tools must use builtin_tools param
                tools=[fetch_url_with_jina],  # Custom tools use regular tools param
            )

            # Since this is running in a thread pool (via _execute_url_individual),
            # we can create a new event loop for this thread.

            async def _run_async() -> Any:
                return await agent.run(prompt)

            # Create a new event loop for this thread to avoid "Event loop is closed" errors
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_run_async())
            finally:
                loop.close()

        except Exception as e:
            msg = f"Failed to enrich URL {url}: {e}"
            raise EnrichmentExecutionError(msg) from e
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
            except Exception as e:
                msg = f"Failed to prepare URL task {task.get('task_id')}: {e}"
                logger.exception(msg)
                if self.task_store:
                    self.task_store.mark_failed(task.get("task_id"), msg)

        return tasks_data

    @property
    def enrichment_config(self) -> EnrichmentSettings:
        """Get effective enrichment configuration."""
        if self._enrichment_config_override:
            return self._enrichment_config_override
        # Fallback to context config if available
        if hasattr(self.ctx, "config"):
            return self.ctx.config.enrichment
        # Last resort fallback (should not happen in normal pipeline)
        return EnrichmentSettings()

    def _determine_concurrency(self, task_count: int) -> int:
        """Determine optimal concurrency based on available API keys.

        Auto-detects number of API keys and uses them in parallel instead of
        sequential rotation.

        Behavior:
        - max_concurrent_enrichments = None (default): Auto-scale to num_keys
        - max_concurrent_enrichments = 1: Explicitly disable auto-scaling (sequential)
        - max_concurrent_enrichments = N: Use exactly N concurrent requests
        """
        from egregora.llm.api_keys import get_google_api_keys

        # Get API keys
        api_keys = get_google_api_keys()
        num_keys = len(api_keys) if api_keys else 1

        # Get configured concurrency (None means auto-scale)
        enrichment_concurrency = getattr(
            self.enrichment_config,
            "max_concurrent_enrichments",
            None,
        )

        # Auto-Parallelization: If None (not configured), auto-scale to match available keys
        if enrichment_concurrency is None:
            logger.info("Auto-scaling concurrency to match available API keys: %d", num_keys)
            enrichment_concurrency = num_keys

        global_concurrency = getattr(self.ctx.config.quota, "concurrency", num_keys)

        # Calculate effective concurrency
        # We cap at num_keys to avoid rate limits on single keys (unless rotation handles it,
        # but concurrent requests on one key is risky for free tier).
        # We also respect global quota.
        max_concurrent = min(enrichment_concurrency, global_concurrency, task_count)

        # If we have more tasks/concurrency allowed than keys, we rely on rotation OR key reuse?
        # Story 6 implies "throughput using all keys in parallel".
        # If enrichment_concurrency > num_keys, we are sending multiple requests per key?
        # That's fine if allowed. But "Set max_concurrent_enrichments = key count" suggests 1:1 mapping.

        # Let's ensure we use at least key count if allowed.

        logger.info(
            "Processing %d enrichment tasks with max concurrency of %d "
            "(API keys: %d, enrichment limit: %d, global limit: %d)",
            task_count,
            max_concurrent,
            num_keys,
            enrichment_concurrency,
            global_concurrency,
        )

        return max_concurrent

    def _execute_url_enrichments(
        self, tasks_data: list[dict[str, Any]], max_concurrent: int
    ) -> list[tuple[dict, EnrichmentOutput | None, str | None]]:
        """Execute URL enrichments based on configured strategy."""
        strategy = getattr(self.enrichment_config, "strategy", "individual")
        total = len(tasks_data)

        # Use single-call batch for batch_all strategy with multiple URLs
        if strategy == "batch_all" and total > 1:
            try:
                logger.info("[URLEnricher] Using single-call batch mode for %d URLs", total)
                return self._execute_url_single_call(tasks_data)
            except Exception as single_call_exc:
                logger.warning(
                    "[URLEnricher] Single-call batch failed (%s), falling back to individual",
                    single_call_exc,
                )

        # Individual calls (default fallback)
        return self._execute_url_individual(tasks_data, max_concurrent)

    def _execute_url_individual(
        self, tasks_data: list[dict[str, Any]], max_concurrent: int
    ) -> list[tuple[dict, EnrichmentOutput | None, str | None]]:
        """Execute URL enrichments individually with model rotation."""
        results: list[tuple[dict, EnrichmentOutput | None, str | None]] = []
        total = len(tasks_data)
        last_log_time = time.time()

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_task = {executor.submit(self._enrich_single_url, td): td for td in tasks_data}
            for i, future in enumerate(as_completed(future_to_task), 1):
                try:
                    results.append(future.result())

                    # Heartbeat logging
                    if time.time() - last_log_time > HEARTBEAT_INTERVAL:
                        logger.info("[Heartbeat] URL Enrichment: %d/%d (%.1f%%)", i, total, (i / total) * 100)
                        last_log_time = time.time()

                except EnrichmentExecutionError as exc:
                    task = future_to_task[future]["task"]
                    # Log as error but maybe without full stack trace if we trust the message?
                    # For now, keep full trace as it helps debugging.
                    logger.error(
                        "Enrichment execution failed for %s: %s", task["task_id"], exc, exc_info=True
                    )
                    results.append((task, None, str(exc)))
                except Exception as exc:
                    task = future_to_task[future]["task"]
                    logger.exception("Unexpected error during enrichment for %s", task["task_id"])
                    results.append((task, None, str(exc)))

        logger.info("[Enrichment] URL tasks complete: %d/%d", len(results), total)
        return results

    # TODO: [Taskmaster] Decompose complex batch execution method
    def _execute_url_single_call(
        self, tasks_data: list[dict[str, Any]]
    ) -> list[tuple[dict, EnrichmentOutput | None, str | None]]:
        """Execute all URL enrichments in a single API call.

        Sends all URLs together with a combined prompt asking for JSON dict result.
        """
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            msg = "GOOGLE_API_KEY or GEMINI_API_KEY required for URL enrichment"
            raise ValueError(msg)

        client = genai.Client(api_key=api_key)

        # Extract URLs from tasks
        urls = []
        for td in tasks_data:
            task = td["task"]
            payload = task.get("_parsed_payload") or json.loads(task.get("payload", "{}"))
            url = payload.get("url", "")
            urls.append(url)

        # Render prompt from Jinja template
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None
        combined_prompt = render_prompt(
            "enrichment.jinja",
            mode="url_batch",
            prompts_dir=prompts_dir,
            url_count=len(urls),
            urls_json=json.dumps(urls),
            pii_prevention=getattr(self.ctx.config.privacy, "pii_prevention", None),
        ).strip()

        # Build model+key rotator if enabled
        rotation_enabled = getattr(self.enrichment_config, "model_rotation_enabled", True)
        rotation_models = getattr(self.enrichment_config, "rotation_models", None)

        if rotation_enabled:
            from egregora.llm.providers.model_key_rotator import ModelKeyRotator

            rotator = ModelKeyRotator(models=rotation_models)

            def call_with_model_and_key(model: str, api_key: str) -> str:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=cast("Any", [{"parts": [{"text": combined_prompt}]}]),
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                return response.text or ""

            response_text = rotator.call_with_rotation(call_with_model_and_key)
        else:
            # No rotation - use configured model and API key
            model_name = self.ctx.config.models.enricher
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=cast("Any", [{"parts": [{"text": combined_prompt}]}]),
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            response_text = response.text or ""

        logger.debug(
            "[URLEnricher] Single-call response received (length: %d)",
            len(response_text) if response_text else 0,
        )

        # Parse JSON response
        try:
            results_dict = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning("[URLEnricher] Failed to parse JSON response: %s", e)
            msg = f"Failed to parse batch response: {e}"
            raise EnrichmentParsingError(msg) from e

        # Convert to result tuples
        results: list[tuple[dict, EnrichmentOutput | None, str | None]] = []
        for td in tasks_data:
            task = td["task"]
            payload = task.get("_parsed_payload") or json.loads(task.get("payload", "{}"))
            url = payload.get("url", "")

            enrichment = results_dict.get(url, {})
            if enrichment:
                # Build EnrichmentOutput from result
                slug = enrichment.get("slug", "")
                title = enrichment.get("title") or slug.replace("-", " ").title()
                tags = enrichment.get("tags", [])
                summary = enrichment.get("summary", "")
                takeaways = enrichment.get("key_takeaways", [])

                # Build markdown from enrichment data
                takeaways_md = "\n".join(f"- {t}" for t in takeaways) if takeaways else ""
                markdown = f"""# {slug}

## Summary
{summary}

## Key Takeaways
{takeaways_md}

---
*Source: [{url}]({url})*
"""
                output = EnrichmentOutput(slug=slug, markdown=markdown, title=title, tags=tags)
                results.append((task, output, None))
                logger.info("[URLEnricher] Processed %s via single-call batch", url)
            else:
                results.append((task, None, f"No result for {url}"))

        logger.info("[URLEnricher] Single-call batch complete: %d/%d", len(results), len(tasks_data))
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
                        "title": output.title or slug_value.replace("-", " ").title(),
                        "tags": output.tags or [],
                        "date": datetime.now(UTC).isoformat(),
                        "nav_exclude": True,
                        "hide": ["navigation"],
                    },
                    id=slug_value,  # Semantic ID
                )

                # Main Architecture: Use ContentLibrary if available
                if self.ctx.library:
                    cast("Any", self.ctx.library).save(doc)
                elif self.ctx.output_sink:
                    self.ctx.output_sink.persist(doc)

                metadata = payload["message_metadata"]
                row = _create_enrichment_row(metadata, "URL", url, doc.document_id, media_identifier=url)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])
            except Exception as exc:
                logger.exception("Failed to persist enrichment for %s", task["task_id"])
                self.task_store.mark_failed(task["task_id"], f"Persistence error: {exc!s}")

        if new_rows:
            try:
                t = ibis.memtable(new_rows)
                self.ctx.storage.write_table(t, "messages", mode="append")
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
        texts: list[str] = []
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

                # Stage the file to disk (ephemeral)
                try:
                    staged_path = self._stage_file(task, payload)
                except MediaStagingError as exc:
                    logger.warning("Failed to stage media for task %s: %s", task["task_id"], exc)
                    self.task_store.mark_failed(task["task_id"], str(exc))
                    continue

                # Store staged path in task for later persistence
                task["_staged_path"] = str(staged_path)

                filename = payload["filename"]
                media_type = payload["media_type"]

                media_part = self._prepare_media_content(staged_path, media_type)

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
                                    media_part,
                                ]
                            }
                        ],
                        "config": {},
                    }
                )
                task_map[tag] = task

            except Exception as exc:
                logger.exception("Failed to prepare media task %s", task.get("task_id"))
                self.task_store.mark_failed(task.get("task_id"), str(exc))

        return requests, task_map

    # TODO: [Taskmaster] Simplify complex file staging logic
    def _stage_file(self, task: dict[str, Any], payload: dict[str, Any]) -> Path:
        """Extract media file from ZIP to ephemeral staging directory."""
        original_filename = payload.get("original_filename") or payload.get("filename")
        if not original_filename:
            msg = "No filename in task payload"
            raise MediaStagingError(msg)

        target_lower = original_filename.lower()

        zf = self.zip_handle
        media_index = self.media_index
        should_close = False

        # Ensure ZIP handle is available, opening it if necessary.
        if zf is None:
            input_path = self.ctx.input_path
            if not input_path or not input_path.exists():
                msg = f"Input path not available for media task {task['task_id']}"
                raise MediaStagingError(msg)
            try:
                zf = zipfile.ZipFile(input_path, "r")
                should_close = True
                media_index = {
                    Path(info.filename).name.lower(): info.filename
                    for info in zf.infolist()
                    if not info.is_dir()
                }
            except (OSError, zipfile.BadZipFile) as exc:
                msg = f"Failed to open source ZIP: {exc}"
                raise MediaStagingError(msg) from exc

        try:
            full_path = media_index.get(target_lower)
            if not full_path:
                msg = f"Media file {original_filename} not found in ZIP"
                raise MediaStagingError(msg)

            safe_name = f"{task['task_id']}_{Path(full_path).name}"
            target_path = Path(self.staging_dir.name) / safe_name

            if target_path.exists():
                return target_path

            with zf.open(full_path) as source, target_path.open("wb") as dest:
                shutil.copyfileobj(source, dest)

            self.staged_files.add(str(target_path))
            return target_path
        except Exception as exc:
            msg = f"Failed to stage media file {original_filename}: {exc}"
            raise MediaStagingError(msg) from exc
        finally:
            if should_close and zf:
                zf.close()

    def _prepare_media_content(self, file_path: Path, mime_type: str) -> dict[str, Any]:
        """Prepare media content for API request, using File API for large files."""
        # Threshold: 20 MB
        params = getattr(self.ctx.config.enrichment, "large_file_threshold_mb", 20)
        threshold_bytes = params * 1024 * 1024

        file_size = file_path.stat().st_size

        if file_size > threshold_bytes:
            from google import genai

            logger.info(
                "File %s is %.2f MB (threshold: %d MB), using File API upload",
                file_path.name,
                file_size / (1024 * 1024),
                params,
            )

            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                msg = "API key required for file upload"
                raise ValueError(msg)

            client = genai.Client(api_key=api_key)

            # Upload file
            # Note: client.files.upload returns a File object with 'uri'
            uploaded_file = client.files.upload(file=str(file_path), config={"mime_type": mime_type})
            logger.info("Uploaded file %s to %s", file_path.name, uploaded_file.uri)

            return {"fileData": {"mimeType": mime_type, "fileUri": uploaded_file.uri}}
        # Inline base64 for small files
        file_bytes = file_path.read_bytes()
        b64_data = base64.b64encode(file_bytes).decode("utf-8")
        return {
            "inlineData": {
                "mimeType": mime_type,
                "data": b64_data,
            }
        }

    def _execute_media_batch(
        self, requests: list[dict[str, Any]], task_map: dict[str, dict[str, Any]]
    ) -> list[Any]:
        """Execute media enrichments based on configured strategy."""
        model_name = self.ctx.config.models.enricher_vision
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            msg = "GOOGLE_API_KEY or GEMINI_API_KEY required for media enrichment"
            raise ValueError(msg)

        # Use strategy-based dispatch
        strategy = getattr(self.enrichment_config, "strategy", "individual")
        if strategy == "batch_all" and len(requests) > 1:
            try:
                logger.info("[MediaEnricher] Using single-call batch mode for %d images", len(requests))
                return self._execute_media_single_call(requests, task_map, model_name, api_key)
            except (google_exceptions.GoogleAPICallError, EnrichmentParsingError) as single_call_exc:
                logger.warning(
                    "[MediaEnricher] Single-call batch failed (%s), falling back to standard batch",
                    single_call_exc,
                )

        # Standard batch API (one request per image)
        model = GoogleBatchModel(api_key=api_key, model_name=model_name)
        try:
            return model.run_batch(requests)
        except (UsageLimitExceeded, ModelHTTPError, google_exceptions.GoogleAPICallError) as batch_exc:
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

        # Strip prefix for direct API calls
        if model_name.startswith("google-gla:"):
            model_name = model_name.removeprefix("google-gla:")

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
                    elif "fileData" in part:
                        parts.append({"fileData": part["fileData"]})

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
        request_parts = [{"text": combined_prompt}, *parts]

        # Build model+key rotator if enabled
        from egregora.llm.providers.model_key_rotator import ModelKeyRotator

        rotation_enabled = getattr(self.enrichment_config, "model_rotation_enabled", True)
        rotation_models = getattr(self.enrichment_config, "rotation_models", None)

        if rotation_enabled:
            rotator = ModelKeyRotator(models=rotation_models)

            def call_with_model_and_key(model: str, api_key: str) -> str:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=cast("Any", [{"parts": request_parts}]),
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                return response.text or ""

            response_text = rotator.call_with_rotation(call_with_model_and_key)
        else:
            # No rotation - use configured model and API key
            response = client.models.generate_content(
                model=model_name,
                contents=cast("Any", [{"parts": request_parts}]),
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            response_text = response.text if response.text else ""

        logger.debug(
            "[MediaEnricher] Single-call response received. Length: %d characters.", len(response_text)
        )

        try:
            results_dict = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning("[MediaEnricher] Failed to parse JSON response: %s", e)
            msg = f"Failed to parse batch response: {e}"
            raise EnrichmentParsingError(msg) from e

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

        # Strip prefix for direct API calls
        if model_name.startswith("google-gla:"):
            model_name = model_name.removeprefix("google-gla:")

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

            try:
                task_result = self._parse_media_result(res, task)
            except EnrichmentParsingError as exc:
                logger.warning("Enrichment parsing failed for task %s: %s", task.get("task_id"), exc)
                self.task_store.mark_failed(task["task_id"], str(exc))
                continue

            payload, output = task_result
            slug_value = output.slug
            markdown = output.markdown
            filename = payload["filename"]
            media_type = payload["media_type"]
            media_id = payload.get("media_id")

            # Use staged path if available
            staged_path = task.get("_staged_path")
            source_path = None

            if staged_path and Path(staged_path).exists():
                source_path = staged_path
            else:
                # Fallback to re-extraction (should be rare if staging works)
                re_staged = self._stage_file(task, payload)
                if re_staged:
                    source_path = str(re_staged)
                else:
                    logger.warning("Could not stage media file for persistence: %s", filename)
                    self.task_store.mark_failed(task["task_id"], "Failed to stage media file")
                    continue

            # Determine subfolder based on media_type
            from egregora.ops.media import get_media_subfolder

            extension = Path(filename).suffix
            media_subdir = get_media_subfolder(extension)

            # Use slug-based filename
            final_filename = f"{slug_value}{extension}"

            # Main Architecture: Set suggested_path to ensure correct filesystem placement
            suggested_path = f"media/{media_subdir}/{final_filename}"

            # Create media document with slug-based metadata
            media_metadata = {
                "original_filename": payload.get("original_filename"),
                "filename": final_filename,
                "media_type": media_type,
                "slug": slug_value,
                "nav_exclude": True,
                "hide": ["navigation"],
                "source_path": source_path,  # Path to staged file for efficient move
                "media_subdir": media_subdir,
            }

            # Persist the actual media file
            # We pass empty bytes for content because source_path is provided
            media_doc = Document(
                content=b"",
                type=DocumentType.MEDIA,
                metadata=media_metadata,
                id=media_id if media_id else str(uuid.uuid4()),
                parent_id=None,  # Media files have no parent document
                suggested_path=suggested_path,
            )

            try:
                if self.ctx.library:
                    cast("Any", self.ctx.library).save(media_doc)
                elif self.ctx.output_sink:
                    self.ctx.output_sink.persist(media_doc)
                logger.info("Persisted enriched media: %s -> %s", filename, media_doc.metadata["filename"])
            except Exception as exc:
                logger.exception("Failed to persist media file %s", filename)
                self.task_store.mark_failed(task["task_id"], f"Persistence failed: {exc}")
                continue

            # Create and persist the enrichment text document (description)
            enrichment_metadata = {
                "filename": final_filename,
                "original_filename": payload.get("original_filename"),  # Preserve original
                "media_type": media_type,
                "parent_path": suggested_path,
                "slug": slug_value,
                "title": output.title if output else slug_value.replace("-", " ").title(),
                "tags": output.tags if output else [],
                "date": datetime.now(UTC).isoformat(),
                "nav_exclude": True,
                "hide": ["navigation"],
            }

            # Map media_type to specific DocumentType for folder organization
            media_type_to_doc_type = {
                "image": DocumentType.ENRICHMENT_IMAGE,
                "video": DocumentType.ENRICHMENT_VIDEO,
                "audio": DocumentType.ENRICHMENT_AUDIO,
            }
            doc_type = media_type_to_doc_type.get(media_type, DocumentType.ENRICHMENT_MEDIA)

            doc = Document(
                content=markdown,
                type=doc_type,
                metadata=enrichment_metadata,
                id=slug_value,
                parent_id=None,  # No parent document needed - slug + filename uniquely identify media
            )

            if self.ctx.library:
                cast("Any", self.ctx.library).save(doc)
            elif self.ctx.output_sink:
                self.ctx.output_sink.persist(doc)

            metadata = payload["message_metadata"]
            row = _create_enrichment_row(
                metadata, "Media", filename, doc.document_id, media_identifier=media_id
            )
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
                # Use parameterized queries to prevent SQL injection
                try:
                    # Update text column using parameterized query
                    # Note: This updates ALL messages containing this ref.
                    query = "UPDATE messages SET text = replace(text, ?, ?) WHERE text LIKE ?"
                    self.ctx.storage.execute_sql(query, [original_ref, new_path, f"%{original_ref}%"])
                except duckdb.Error as exc:
                    logger.warning("Failed to update message references for %s: %s", original_ref, exc)

            self.task_store.mark_completed(task["task_id"])

        if new_rows:
            try:
                t = ibis.memtable(new_rows)
                self.ctx.storage.write_table(t, "messages", mode="append")
                logger.info("Inserted %d media enrichment rows", len(new_rows))
            except (IbisError, duckdb.Error):
                logger.exception("Failed to insert media enrichment rows")

        return len(results)

    # TODO: [Taskmaster] Improve brittle JSON parsing from LLM output
    def _parse_media_result(self, res: Any, task: dict[str, Any]) -> tuple[dict[str, Any], EnrichmentOutput]:
        text = self._extract_text(res.response)
        try:
            clean_text = text.strip()
            clean_text = clean_text.removeprefix("```json")
            clean_text = clean_text.removeprefix("```")
            clean_text = clean_text.removesuffix("```")

            data = json.loads(clean_text.strip())
            slug = data.get("slug")
            markdown = data.get("markdown")
            title = data.get("title")
            tags = data.get("tags", [])

            payload = task["_parsed_payload"]
            filename = payload.get("filename", "")

            # Normalize slug first to use in filename construction
            slug_value = _normalize_slug(slug, payload["filename"]) if slug else None

            # Fallback logic for missing markdown
            if not markdown and slug_value:
                description = data.get("description", "")
                alt_text = data.get("alt_text", "")

                # Construct final filename to match what will be persisted
                ext = Path(filename).suffix
                final_filename = f"{slug_value}{ext}"

                if description or alt_text:
                    markdown = f"""# {slug_value}

![{alt_text}]({final_filename})

## Description
{description}

## Tags
"""
                    logger.info("Constructed fallback markdown for %s -> %s", filename, final_filename)

            if not slug_value or not markdown:
                msg = "Missing slug or markdown"
                raise EnrichmentParsingError(msg)

            output = EnrichmentOutput(slug=slug_value, markdown=markdown, title=title, tags=tags)
            return payload, output

        except (json.JSONDecodeError, EnrichmentSlugError) as exc:
            msg = f"Failed to parse media result for task {task.get('task_id')}: {exc}"
            raise EnrichmentParsingError(msg) from exc
