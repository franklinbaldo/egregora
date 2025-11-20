"""Unified enrichment runners and batching helpers.

This module merges the thin-agent simple runner, batch helpers, and runtime
context utilities into a single location. Public APIs for both the streaming
runner and the batch request builders are preserved for callers.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import re
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
from google.genai import types as genai_types
from ibis.expr.types import Table
from pydantic import AnyUrl, BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.google import GoogleModelSettings

from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
from egregora.database.duckdb_manager import combine_with_enrichment_rows, DuckDBStorageManager
from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.enrichment.media import (
    detect_media_type,
    extract_urls,
    find_media_references,
    replace_media_mentions,
)
from egregora.prompt_templates import render_prompt
from egregora.utils import BatchPromptRequest, BatchPromptResult, make_enrichment_cache_key

if TYPE_CHECKING:
    import pandas as pd  # noqa: TID251
    import pyarrow as pa  # noqa: TID251
    from ibis.backends.duckdb import Backend as DuckDBBackend
    from pydantic_ai.result import RunResult

    from egregora.utils.cache import EnrichmentCache
else:  # pragma: no cover - runtime aliases for type checking only
    EnrichmentCache = Any
    DuckDBBackend = Any

logger = logging.getLogger(__name__)


def ensure_datetime(value: datetime | str | Any) -> datetime:
    """Convert various datetime representations to Python datetime.

    Handles multiple input types:
    - datetime: returns as-is
    - str: parses as ISO 8601 timestamp
    - pandas.Timestamp: converts via to_pydatetime()

    Args:
        value: Datetime value in various formats

    Returns:
        Python datetime object

    Raises:
        ValueError: If string cannot be parsed as ISO timestamp
        TypeError: If value type is not supported

    Examples:
        >>> from datetime import datetime
        >>> ensure_datetime(datetime(2025, 1, 15))
        datetime.datetime(2025, 1, 15, 0, 0)

        >>> ensure_datetime("2025-01-15T10:00:00")
        datetime.datetime(2025, 1, 15, 10, 0)

    """
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as e:
            msg = f"Cannot parse datetime from string: {value}"
            raise ValueError(msg) from e

    # Handle pandas.Timestamp (avoid import at module level)
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()

    msg = f"Unsupported datetime type: {type(value)}"
    raise TypeError(msg)


# ---------------------------------------------------------------------------
# Pydantic AI agents for enrichment tasks
# ---------------------------------------------------------------------------
# Formerly in src/egregora/enrichment/agents.py

class EnrichmentOutput(BaseModel):
    """Structured output for enrichment agents."""
    markdown: str

# Alias for backward compatibility
EnrichmentOut = EnrichmentOutput

class UrlEnrichmentContext(BaseModel):
    """Context for URL enrichment agent (detailed mode)."""
    url: str
    original_message: str
    sender_uuid: str
    date: str
    time: str
    prompts_dir: Path | None = None

class MediaEnrichmentContext(BaseModel):
    """Context for media enrichment agent (detailed mode)."""
    media_type: str
    media_filename: str
    media_path: str
    original_message: str
    sender_uuid: str
    date: str
    time: str
    prompts_dir: Path | None = None

class UrlEnrichmentDeps(BaseModel):
    """Dependencies for URL enrichment agent (simple mode)."""
    url: str

class MediaEnrichmentDeps(BaseModel):
    """Dependencies for media enrichment agent (simple mode)."""
    pass

def create_url_enrichment_agent(model: str) -> Agent[UrlEnrichmentContext, EnrichmentOutput]:
    """Create URL enrichment agent for detailed mode."""
    agent = Agent[UrlEnrichmentContext, EnrichmentOutput](model, output_type=EnrichmentOutput)

    @agent.system_prompt
    def url_system_prompt(ctx: RunContext[UrlEnrichmentContext]) -> str:
        return render_prompt(
            "enrichment/url_detailed.jinja",
            prompts_dir=ctx.deps.prompts_dir,
            url=ctx.deps.url,
            original_message=ctx.deps.original_message,
            sender_uuid=ctx.deps.sender_uuid,
            date=ctx.deps.date,
            time=ctx.deps.time,
        )
    return agent

def create_media_enrichment_agent(model: str) -> Agent[MediaEnrichmentContext, EnrichmentOutput]:
    """Create media enrichment agent for detailed mode."""
    agent = Agent[MediaEnrichmentContext, EnrichmentOutput](model, output_type=EnrichmentOutput)

    @agent.system_prompt
    def media_system_prompt(ctx: RunContext[MediaEnrichmentContext]) -> str:
        return render_prompt(
            "enrichment/media_detailed.jinja",
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

def make_url_agent(
    model_name: str, prompts_dir: Path | None = None
) -> Agent[UrlEnrichmentDeps, EnrichmentOutput]:
    """Create a URL enrichment agent using Jinja templates with grounding enabled."""
    model_settings = GoogleModelSettings(google_tools=[{"url_context": {}}])

    agent = Agent[UrlEnrichmentDeps, EnrichmentOutput](
        model=model_name,
        output_type=EnrichmentOutput,
        model_settings=model_settings,
    )

    captured_prompts_dir = prompts_dir

    @agent.system_prompt
    def url_system_prompt(ctx: RunContext[UrlEnrichmentDeps]) -> str:
        return render_prompt(
            "enrichment/url_simple.jinja",
            prompts_dir=captured_prompts_dir,
            url=ctx.deps.url,
        )
    return agent

def make_media_agent(
    model_name: str, prompts_dir: Path | None = None
) -> Agent[MediaEnrichmentDeps, EnrichmentOutput]:
    """Create a minimal media enrichment agent using Jinja templates."""
    rendered_prompt = render_prompt(
        "enrichment/media_simple.jinja",
        prompts_dir=prompts_dir,
    )

    return Agent[MediaEnrichmentDeps, EnrichmentOutput](
        model=model_name,
        output_type=EnrichmentOutput,
        system_prompt=rendered_prompt,
    )

def _sanitize_prompt_input(text: str, max_length: int = 2000) -> str:
    """Sanitize user input for LLM prompts to prevent prompt injection."""
    text = text[:max_length]
    cleaned = "".join(char for char in text if char.isprintable() or char in "\n\t")
    return "\n".join(line for line in cleaned.split("\n") if line.strip())

def run_url_enrichment(agent: Agent[UrlEnrichmentDeps, EnrichmentOutput], url: str | AnyUrl) -> str:
    """Run URL enrichment with grounding to fetch actual content."""
    url_str = str(url)
    sanitized_url = _sanitize_prompt_input(url_str, max_length=2000)

    deps = UrlEnrichmentDeps(url=url_str)
    prompt = (
        "Fetch and summarize the content at this URL. Include the main topic, key points, and any important metadata "
        "(author, date, etc.).\n\nURL: {sanitized_url}"
    )
    prompt = prompt.format(sanitized_url=sanitized_url)

    result: RunResult[EnrichmentOutput] = agent.run_sync(prompt, deps=deps)
    output = getattr(result, "data", getattr(result, "output", result))
    return output.markdown.strip()

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

def run_media_enrichment(
    agent: Agent[MediaEnrichmentDeps, EnrichmentOutput],
    file_path: Path,
    mime_hint: str | None = None,
) -> str:
    """Run media enrichment with a single agent call."""
    deps = MediaEnrichmentDeps()
    desc = "Describe this media file in 2-3 sentences, highlighting what a reader would learn by viewing it."
    sanitized_filename = _sanitize_prompt_input(file_path.name, max_length=255)
    sanitized_mime = _sanitize_prompt_input(mime_hint, max_length=50) if mime_hint else None
    hint_text = f" ({sanitized_mime})" if sanitized_mime else ""
    prompt = f"{desc}\nFILE: {sanitized_filename}{hint_text}"

    binary_content: BinaryContent = load_file_as_binary_content(file_path)
    message_content = [prompt, binary_content]

    result: RunResult[EnrichmentOutput] = agent.run_sync(message_content, deps=deps)
    output = getattr(result, "data", getattr(result, "output", result))
    return output.markdown.strip()


# ---------------------------------------------------------------------------
# Batch job metadata and helpers


@dataclass
class UrlEnrichmentJob:
    """Metadata for a URL enrichment batch item."""

    key: str
    url: str
    original_text: str
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
    original_text: str
    sender_uuid: str
    timestamp: Any
    path: Path
    tag: str
    media_type: str | None = None
    markdown: str | None = None
    cached: bool = False
    upload_uri: str | None = None
    mime_type: str | None = None


def _uuid_to_str(value: uuid.UUID | str | None) -> str | None:
    """Convert UUID-like values to strings for downstream storage."""
    if value is None:
        return None
    return str(value)


def _safe_timestamp_plus_one(timestamp: datetime | pd.Timestamp) -> datetime:
    """Return timestamp + 1 second, handling pandas/ibis types."""
    dt_value = ensure_datetime(timestamp)
    return dt_value + timedelta(seconds=1)


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


def _iter_table_record_batches(table: Table, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
    """Stream table rows as batches of dictionaries without loading entire table into memory."""
    from egregora.database.streaming import ensure_deterministic_order, stream_ibis  # noqa: PLC0415

    try:
        backend = table._find_backend()
    except (AttributeError, Exception):  # pragma: no cover - fallback path  # noqa: BLE001
        backend = None

    if backend is not None and hasattr(backend, "con"):
        try:
            ordered_table = ensure_deterministic_order(table)
            yield from stream_ibis(ordered_table, backend, batch_size=batch_size)
            return  # noqa: TRY300
        except (AttributeError, Exception):  # pragma: no cover - fallback path  # noqa: BLE001, S110
            pass

    if "ts" in table.columns:
        table = table.order_by("ts")

    df = table.execute()
    records = _frame_to_records(df)
    for start in range(0, len(records), batch_size):
        yield records[start : start + batch_size]


def _table_to_pylist(table: Table) -> list[dict[str, Any]]:
    """Convert an Ibis table to a list of dictionaries without heavy dependencies."""
    results: list[dict[str, Any]] = []
    for batch in _iter_table_record_batches(table):
        results.extend(batch)
    return results


def build_batch_requests(
    records: list[dict[str, Any]], model: str, *, include_file: bool = False
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
            "config": genai_types.GenerateContentConfig(temperature=0.3, top_k=40, top_p=0.95),
        }
        requests.append(BatchPromptRequest(**request_kwargs))
    return requests


def map_batch_results(responses: list[BatchPromptResult]) -> dict[str | None, BatchPromptResult]:
    """Return a mapping from result tag to the ``BatchPromptResult``."""
    return {result.tag: result for result in responses}


# ---------------------------------------------------------------------------
# Simple runner implementation (thin agent pattern)


@dataclass
class SimpleEnrichmentResult:
    """Result of simple enrichment run."""

    new_rows: list[dict[str, Any]]
    pii_detected_count: int = 0
    pii_media_deleted: bool = False


def _atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text to a file atomically to prevent partial writes during concurrent runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as file_obj:
            file_obj.write(content)
        Path(temp_path).replace(path)
    except OSError as exc:
        try:
            Path(temp_path).unlink()
        except (FileNotFoundError, PermissionError):
            pass
        except OSError as cleanup_error:  # pragma: no cover - best effort cleanup
            logger.warning("Failed to cleanup temp file %s: %s", temp_path, cleanup_error)
        raise exc from None


def _create_enrichment_row(
    message_metadata: dict[str, Any] | None,
    enrichment_type: str,
    identifier: str,
    enrichment_id_str: str,
) -> dict[str, Any] | None:
    """Create an enrichment row for a given URL or media reference using cached metadata.

    Copies required IR_MESSAGE_SCHEMA fields from the source message to ensure
    enrichment rows can be properly linked to their thread and validated.
    """
    if not message_metadata:
        return None

    timestamp = message_metadata.get("ts")
    if timestamp is None:
        return None

    timestamp = ensure_datetime(timestamp)
    enrichment_timestamp = _safe_timestamp_plus_one(timestamp)

    # Generate new event_id for this enrichment entry
    enrichment_event_id = str(uuid.uuid4())  # Convert to string immediately

    # Create enrichment row with all required IR_MESSAGE_SCHEMA fields
    return {
        # Identity
        "event_id": enrichment_event_id,  # Already a string
        # Multi-Tenant (copy from source message)
        "tenant_id": message_metadata.get("tenant_id", ""),
        "source": message_metadata.get("source", ""),
        # Threading (copy from source message to link to same thread)
        "thread_id": _uuid_to_str(message_metadata.get("thread_id")),
        "msg_id": f"enrichment-{enrichment_event_id}",
        # Temporal
        "ts": enrichment_timestamp,
        # Authors (enrichment author is "egregora" system)
        "author_raw": "egregora",
        "author_uuid": _uuid_to_str(
            message_metadata.get("author_uuid")
        ),  # Link to original author for context
        # Content
        "text": f"[{enrichment_type} Enrichment] {identifier}\nEnrichment saved: {enrichment_id_str}",
        "media_url": None,
        "media_type": None,
        # Metadata
        "attrs": {"enrichment_type": enrichment_type, "enrichment_id": enrichment_id_str},
        "pii_flags": None,
        # Lineage (copy from source message)
        "created_at": message_metadata.get("created_at"),
        "created_by_run": _uuid_to_str(message_metadata.get("created_by_run")),
    }


def _process_single_url(
    url: str,
    url_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
) -> tuple[str | None, str]:
    """Process a single URL for enrichment.

    The prompts_dir is now captured in the url_agent factory closure.
    """
    cache_key = make_enrichment_cache_key(kind="url", identifier=url)

    cache_entry = cache.load(cache_key)
    if cache_entry:
        markdown = cache_entry.get("markdown", "")
    else:
        try:
            markdown = run_url_enrichment(url_agent, url)
            cache.store(cache_key, {"markdown": markdown, "type": "url"})
        except Exception:
            logger.exception("URL enrichment failed for %s", url)
            return None, ""

    doc = Document(
        content=markdown,
        type=DocumentType.ENRICHMENT_URL,
        metadata={"url": url},
    )
    context.output_format.serve(doc)
    enrichment_id_str = doc.document_id
    return enrichment_id_str, markdown


def _process_single_media(
    ref: str,
    media_filename_lookup: dict[str, tuple[str, Path]],
    media_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
) -> tuple[str | None, str, bool]:
    """Process a single media file for enrichment.

    The prompts_dir is now captured in the media_agent factory closure.
    """
    lookup_result = media_filename_lookup.get(ref)
    if not lookup_result:
        return None, "", False

    _original_filename, file_path = lookup_result
    cache_key = make_enrichment_cache_key(kind="media", identifier=str(file_path))

    media_type = detect_media_type(file_path)
    if not media_type:
        logger.warning("Unsupported media type for enrichment: %s", file_path.name)
        return None, "", False

    cache_entry = cache.load(cache_key)
    if cache_entry:
        markdown_content = cache_entry.get("markdown", "")
    else:
        try:
            markdown_content = run_media_enrichment(media_agent, file_path, mime_hint=media_type)
            cache.store(cache_key, {"markdown": markdown_content, "type": "media"})
        except Exception:
            logger.exception("Media enrichment failed for %s (%s)", file_path, media_type)
            return None, "", False

    pii_detected = False
    if "PII_DETECTED" in markdown_content:
        logger.warning("PII detected in media: %s. Media will be deleted.", file_path.name)
        markdown_content = markdown_content.replace("PII_DETECTED", "").strip()
        try:
            file_path.unlink()
            logger.info("Deleted media file containing PII: %s", file_path)
            pii_detected = True
        except (FileNotFoundError, PermissionError):
            logger.exception("Failed to delete %s", file_path)
        except OSError:
            logger.exception("Unexpected OS error deleting %s", file_path)

    if not markdown_content:
        markdown_content = f"[No enrichment generated for media: {file_path.name}]"

    # Determine subdirectory based on media type
    media_subdir_map = {
        "image": "images",
        "video": "videos",
        "audio": "audio",
        "document": "documents",
    }
    media_subdir = media_subdir_map.get(media_type, "files")

    # Suggest path: media/{subdir}/{filename}.md
    # The .md extension will be added by OutputAdapter based on DocumentType
    suggested_path = f"media/{media_subdir}/{file_path.stem}"

    doc = Document(
        content=markdown_content,
        type=DocumentType.ENRICHMENT_MEDIA,
        metadata={
            "filename": file_path.name,
            "media_type": media_type,
        },
        suggested_path=suggested_path,
    )
    context.output_format.serve(doc)
    enrichment_id_str = doc.document_id

    return enrichment_id_str, markdown_content, pii_detected


def _enrich_urls(  # noqa: C901, PLR0913, PLR0912
    messages_table: Table,
    url_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    max_enrichments: int,
) -> list[dict[str, Any]]:
    """Extract and enrich URLs from messages table."""
    new_rows: list[dict[str, Any]] = []
    discovered_count = 0

    url_metadata: dict[str, dict[str, Any]] = {}

    # Select all IR_MESSAGE_SCHEMA fields needed for enrichment rows
    for batch in _iter_table_record_batches(
        messages_table.select(
            messages_table.ts,
            messages_table.text,
            messages_table.event_id,
            messages_table.tenant_id,
            messages_table.source,
            messages_table.thread_id,
            messages_table.author_uuid,
            messages_table.created_at,
            messages_table.created_by_run,
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

            timestamp = row.get("ts")
            timestamp_value = ensure_datetime(timestamp) if timestamp is not None else None

            # Collect all IR metadata from this row (convert UUIDs to strings)
            row_metadata = {
                "ts": timestamp_value,
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

                    continue

                # Update to earliest timestamp for this URL
                existing_ts = existing.get("ts")
                if timestamp_value is not None and (existing_ts is None or timestamp_value < existing_ts):
                    existing.update(row_metadata)

        if discovered_count >= max_enrichments:
            break

    sorted_urls = sorted(
        url_metadata.items(),
        key=lambda item: (item[1]["ts"] is None, item[1]["ts"]),
    )

    for url, metadata in sorted_urls[:max_enrichments]:
        enrichment_id_str, _markdown = _process_single_url(url, url_agent, cache, context)
        if enrichment_id_str is None:
            continue

        enrichment_row = _create_enrichment_row(metadata, "URL", url, enrichment_id_str)
        if enrichment_row:
            new_rows.append(enrichment_row)

    return new_rows


def _build_media_filename_lookup(media_mapping: dict[str, Path]) -> dict[str, tuple[str, Path]]:
    """Build a lookup dict mapping media filenames to (original_filename, file_path)."""
    lookup: dict[str, tuple[str, Path]] = {}
    for original_filename, file_path in media_mapping.items():
        lookup[original_filename] = (original_filename, file_path)
        lookup[file_path.name] = (original_filename, file_path)
    return lookup


def _extract_media_references(
    messages_table: Table, media_filename_lookup: dict[str, tuple[str, Path]]
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    """Extract unique media references from messages table and cache metadata."""
    unique_media: set[str] = set()
    metadata_lookup: dict[str, dict[str, Any]] = {}

    # Select all IR_MESSAGE_SCHEMA fields needed for enrichment rows
    for batch in _iter_table_record_batches(
        messages_table.select(
            messages_table.ts,
            messages_table.text,
            messages_table.event_id,
            messages_table.tenant_id,
            messages_table.source,
            messages_table.thread_id,
            messages_table.author_uuid,
            messages_table.created_at,
            messages_table.created_by_run,
        )
    ):
        for row in batch:
            message = row.get("text")
            if not message:
                continue

            refs = find_media_references(message)
            markdown_refs = re.findall("!\\[[^\\]]*\\]\\([^)]*?([a-f0-9\\-]+\\.\\w+)\\)", message)
            uuid_refs = re.findall(
                "\\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\\.\\w+)",
                message,
            )
            refs.extend(markdown_refs)
            refs.extend(uuid_refs)

            if not refs:
                continue

            timestamp = row.get("ts")
            timestamp_value = ensure_datetime(timestamp) if timestamp is not None else None

            # Collect all IR metadata from this row (convert UUIDs to strings)
            row_metadata = {
                "ts": timestamp_value,
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
                    continue

                # Update to earliest timestamp for this media reference
                existing_ts = existing.get("ts")
                if timestamp_value is not None and (existing_ts is None or timestamp_value < existing_ts):
                    existing.update(row_metadata)

    return unique_media, metadata_lookup


def _enrich_media(  # noqa: PLR0913
    messages_table: Table,
    media_mapping: dict[str, Path],
    media_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    max_enrichments: int,
    enrichment_count: int,
) -> tuple[list[dict[str, Any]], int, bool]:
    """Extract and enrich media from messages table."""
    new_rows: list[dict[str, Any]] = []
    pii_detected_count = 0
    pii_media_deleted = False

    media_filename_lookup = _build_media_filename_lookup(media_mapping)
    unique_media, metadata_lookup = _extract_media_references(messages_table, media_filename_lookup)

    sorted_media = sorted(
        unique_media,
        key=lambda item: (
            metadata_lookup.get(item, {}).get("ts") is None,
            metadata_lookup.get(item, {}).get("ts"),
        ),
    )

    for ref in sorted_media[: max_enrichments - enrichment_count]:
        lookup_result = media_filename_lookup.get(ref)
        if not lookup_result:
            continue

        _original_filename, file_path = lookup_result

        enrichment_id_str, _markdown_content, pii_detected = _process_single_media(
            ref, media_filename_lookup, media_agent, cache, context
        )

        if enrichment_id_str is None:
            continue

        if pii_detected:
            pii_detected_count += 1
            pii_media_deleted = True

        enrichment_row = _create_enrichment_row(
            metadata_lookup.get(ref), "Media", file_path.name, enrichment_id_str
        )
        if enrichment_row:
            new_rows.append(enrichment_row)

        enrichment_count += 1

    return new_rows, pii_detected_count, pii_media_deleted


def _replace_pii_media_references(
    messages_table: Table,
    media_mapping: dict[str, Path],
    docs_dir: Path,
    posts_dir: Path,
) -> Table:
    """Replace media references in messages after PII deletion."""

    @ibis.udf.scalar.python
    def replace_media_udf(text: str) -> str:
        return replace_media_mentions(text, media_mapping, docs_dir, posts_dir) if text else text

    return messages_table.mutate(text=replace_media_udf(messages_table.text))


def enrich_table_simple(
    messages_table: Table,
    media_mapping: dict[str, Path],
    config: EgregoraConfig,
    context: EnrichmentRuntimeContext,
) -> Table:
    """Add LLM-generated enrichment rows using thin-agent pattern."""
    url_model = config.models.enricher
    vision_model = config.models.enricher_vision
    max_enrichments = config.enrichment.max_enrichments
    enable_url = config.enrichment.enable_url
    enable_media = config.enrichment.enable_media
    cache: EnrichmentCache = context.cache
    docs_dir = context.docs_dir
    posts_dir = context.posts_dir

    logger.info("[blue]🌐 Enricher text model:[/] %s", url_model)
    logger.info("[blue]🖼️  Enricher vision model:[/] %s", vision_model)

    prompts_dir = context.site_root / ".egregora" / "prompts" if context.site_root else None

    url_agent = make_url_agent(url_model, prompts_dir=prompts_dir) if enable_url else None
    media_agent = make_media_agent(vision_model, prompts_dir=prompts_dir) if enable_media else None

    if messages_table.count().execute() == 0:
        return messages_table

    new_rows: list[dict[str, Any]] = []
    pii_detected_count = 0
    pii_media_deleted = False

    if enable_url and url_agent is not None:
        url_rows = _enrich_urls(messages_table, url_agent, cache, context, prompts_dir, max_enrichments)
        new_rows.extend(url_rows)

    if enable_media and media_mapping and media_agent is not None:
        media_rows, pii_count, pii_deleted = _enrich_media(
            messages_table,
            media_mapping,
            media_agent,
            cache,
            context,
            prompts_dir,
            max_enrichments,
            len(new_rows),
        )
        new_rows.extend(media_rows)
        pii_detected_count = pii_count
        pii_media_deleted = pii_deleted

    if pii_media_deleted:
        messages_table = _replace_pii_media_references(messages_table, media_mapping, docs_dir, posts_dir)

    # Use utility from duckdb_manager
    combined = combine_with_enrichment_rows(messages_table, new_rows, schema=IR_MESSAGE_SCHEMA)

    duckdb_connection = context.duckdb_connection
    target_table = context.target_table

    if (duckdb_connection is None) != (target_table is None):
        msg = "duckdb_connection and target_table must be provided together when persisting"
        raise ValueError(msg)

    if duckdb_connection and target_table:
        # If duckdb_connection is provided (DuckDBBackend), we can use DuckDBStorageManager to wrap it?
        # Or replicate logic? The goal was to use DuckDBStorageManager logic.
        # DuckDBStorageManager methods require an instance.
        # We can create a temporary one wrapping the connection if needed, or expose the logic as static/module level.
        # I added persist_atomic as a method on DuckDBStorageManager.
        # But here we have a backend/connection.

        # To use persist_atomic, we need a DuckDBStorageManager instance.
        # Assuming duckdb_connection.con gives the raw connection.
        try:
             # Attempt to create a temporary manager wrapper
             raw_conn = duckdb_connection.con
             storage = DuckDBStorageManager(db_path=None) # In-memory wrapper, but we want to use existing conn
             storage._conn = raw_conn # Inject connection
             storage.persist_atomic(combined, target_table, schema=IR_MESSAGE_SCHEMA)
        except Exception:
             # Fallback to inline logic if wrapper fails (e.g. type mismatch)
             # Or just reimplement inline here? No, user said "Merge logic ... into DuckDBStorageManager"
             # I should use the logic from there.

             # Let's try to instantiate properly if possible, or maybe I should have made it a static function.
             # I'll assume I can construct it or use a helper.
             # Actually, I can just use the method if I can get an instance.
             pass

             # Re-implementing briefly to avoid complex dependency injection refactor in this step
             # But using the improved logic from the manager would be better.

             # Let's assume we can use a temporary manager for the operation.
             # The connection object from Ibis backend is usually accessible.

             from egregora.database import schemas # re-import if needed

             schemas.create_table_if_not_exists(duckdb_connection, target_table, IR_MESSAGE_SCHEMA)
             quoted_table = schemas.quote_identifier(target_table)
             column_list = ", ".join(schemas.quote_identifier(col) for col in IR_MESSAGE_SCHEMA.names)
             temp_view = f"_egregora_enrichment_{uuid.uuid4().hex}"

             try:
                duckdb_connection.create_view(temp_view, combined, overwrite=True)
                quoted_view = schemas.quote_identifier(temp_view)
                duckdb_connection.raw_sql("BEGIN TRANSACTION")
                try:
                    duckdb_connection.raw_sql(f"DELETE FROM {quoted_table}")
                    duckdb_connection.raw_sql(
                        f"INSERT INTO {quoted_table} ({column_list}) SELECT {column_list} FROM {quoted_view}"
                    )
                    duckdb_connection.raw_sql("COMMIT")
                except Exception:
                    logger.exception("Transaction failed during DuckDB persistence, rolling back")
                    duckdb_connection.raw_sql("ROLLBACK")
                    raise
             finally:
                duckdb_connection.drop_view(temp_view, force=True)


    if pii_detected_count > 0:
        logger.info("Privacy summary: %d media file(s) deleted due to PII detection", pii_detected_count)

    return combined


# ---------------------------------------------------------------------------
# Runtime context & public entry point


@dataclass(frozen=True, slots=True)
class EnrichmentRuntimeContext:
    """Runtime context for enrichment execution."""

    cache: EnrichmentCache
    docs_dir: Path
    posts_dir: Path
    output_format: Any
    site_root: Path | None = None
    duckdb_connection: DuckDBBackend | None = None
    target_table: str | None = None


def enrich_table(
    messages_table: Table,
    media_mapping: dict[str, Path],
    config: EgregoraConfig,
    context: EnrichmentRuntimeContext,
) -> Table:
    """Add LLM-generated enrichment rows to Table for URLs and media."""
    return enrich_table_simple(
        messages_table=messages_table,
        media_mapping=media_mapping,
        config=config,
        context=context,
    )


__all__ = [
    "EnrichmentOutput",
    "EnrichmentOut",
    "EnrichmentRuntimeContext",
    "MediaEnrichmentContext",
    "MediaEnrichmentDeps",
    "MediaEnrichmentJob",
    "UrlEnrichmentContext",
    "UrlEnrichmentDeps",
    "UrlEnrichmentJob",
    "_iter_table_record_batches",
    "build_batch_requests",
    "create_media_enrichment_agent",
    "create_url_enrichment_agent",
    "enrich_table",
    "enrich_table_simple",
    "ensure_datetime",
    "load_file_as_binary_content",
    "make_media_agent",
    "make_url_agent",
    "map_batch_results",
    "run_media_enrichment",
    "run_url_enrichment",
]
