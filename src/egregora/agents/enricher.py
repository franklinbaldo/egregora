"""Enrichment agent logic for processing URLs and media.

This module implements the enrichment workflow using Pydantic-AI agents, replacing the
legacy batching runners. It provides:
- UrlEnrichmentAgent & MediaEnrichmentAgent
- Orchestration via enrich_table (synchronous)
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

import httpx
import ibis
from ibis.expr.types import Table
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.google import GoogleModelSettings
from ratelimit import limits, sleep_and_retry
from tenacity import Retrying

from egregora.config.settings import EnrichmentSettings, get_google_api_key
from egregora.constants import PrivacyMarkers
from egregora.data_primitives.document import Document
from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.input_adapters.base import MediaMapping
from egregora.models.google_batch import GoogleBatchModel
from egregora.ops.media import (
    detect_media_type,
    extract_urls,
    find_media_references,
    replace_media_mentions,
)
from egregora.resources.prompts import render_prompt
from egregora.utils.batch import RETRY_IF, RETRY_STOP, RETRY_WAIT
from egregora.utils.cache import EnrichmentCache, make_enrichment_cache_key
from egregora.utils.datetime_utils import parse_datetime_flexible
from egregora.utils.metrics import UsageTracker
from egregora.utils.paths import slugify
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


def normalize_slug(candidate: str | None, fallback: str) -> str:
    """Normalize slug from candidate string or fallback."""
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
    quota: Any | None = None  # QuotaTracker
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

    # Wrap the Google batch model so we still satisfy the Agent interface
    model_instance = GoogleBatchModel(api_key=get_google_api_key(), model_name=model)

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
    model_instance = GoogleBatchModel(api_key=get_google_api_key(), model_name=model)
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
# Helper Logic (Synchronous Execution)
# ---------------------------------------------------------------------------


@sleep_and_retry
@limits(calls=100, period=60)
def run_url_enrichment(
    agent: Agent[UrlEnrichmentDeps, EnrichmentOutput],
    url: str,
    prompts_dir: Path | None,
    pii_prevention: dict[str, Any] | None = None,
) -> tuple[EnrichmentOutput, Any]:
    """Run URL enrichment synchronously."""
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
    ).strip()

    for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
        with attempt:
            # Use run_sync for synchronous execution
            result = agent.run_sync(prompt, deps=deps)
    output = getattr(result, "data", getattr(result, "output", result))
    output.markdown = output.markdown.strip()
    return output, result.usage()


@sleep_and_retry
@limits(calls=100, period=60)
def run_media_enrichment(  # noqa: PLR0913
    agent: Agent[MediaEnrichmentDeps, EnrichmentOutput],
    *,
    filename: str,
    mime_hint: str | None,
    prompts_dir: Path | None,
    binary_content: BinaryContent | None = None,
    file_path: Path | None = None,
    media_path: str | None = None,
    pii_prevention: dict[str, Any] | None = None,
) -> tuple[EnrichmentOutput, Any]:
    """Run media enrichment synchronously."""
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
    ).strip()

    payload = binary_content or load_file_as_binary_content(file_path)
    message_content = [prompt, payload]

    for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
        with attempt:
            # Use run_sync for synchronous execution
            result = agent.run_sync(message_content, deps=deps)
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


def create_enrichment_row(
    message_metadata: dict[str, Any] | None,
    enrichment_type: str,
    identifier: str,
    enrichment_id_str: str,
) -> dict[str, Any] | None:
    """Create a new message row for the enrichment data."""
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
# Scheduling (Producer)
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


def replace_pii_media_references(
    messages_table: Table,
    media_mapping: MediaMapping,
) -> Table:
    """Replace media references in messages after PII deletion."""

    @ibis.udf.scalar.python
    def replace_media_udf(text: str) -> str:
        return replace_media_mentions(text, media_mapping) if text else text

    return messages_table.mutate(text=replace_media_udf(messages_table.text))
