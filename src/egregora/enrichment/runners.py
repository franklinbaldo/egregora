"""Unified enrichment runners and batching helpers.

This module merges the thin-agent simple runner, batch helpers, and runtime
context utilities into a single location. Public APIs for both the streaming
runner and the batch request builders are preserved for callers.
"""

from __future__ import annotations

import logging
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

from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
from egregora.database import schemas
from egregora.database.ir_schema import CONVERSATION_SCHEMA
from egregora.enrichment.agents import (
    make_media_agent,
    make_url_agent,
    run_media_enrichment,
    run_url_enrichment,
)
from egregora.enrichment.media import (
    detect_media_type,
    extract_urls,
    find_media_references,
    replace_media_mentions,
)
from egregora.utils import BatchPromptRequest, BatchPromptResult, make_enrichment_cache_key

if TYPE_CHECKING:
    import pandas as pd
    import pyarrow as pa
    from ibis.backends.duckdb import Backend as DuckDBBackend

    from egregora.utils.cache import EnrichmentCache
else:  # pragma: no cover - runtime aliases for type checking only
    EnrichmentCache = Any
    DuckDBBackend = Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Batch job metadata and helpers


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


def _ensure_datetime(value: datetime | pd.Timestamp) -> datetime:
    """Convert pandas/ibis timestamp objects to ``datetime``."""
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


def _safe_timestamp_plus_one(timestamp: datetime | pd.Timestamp) -> datetime:
    """Return timestamp + 1 second, handling pandas/ibis types."""
    dt_value = _ensure_datetime(timestamp)
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
    from egregora.database.streaming import ensure_deterministic_order, stream_ibis

    try:
        backend = table._find_backend()
    except (AttributeError, Exception):  # pragma: no cover - fallback path
        backend = None

    if backend is not None and hasattr(backend, "con"):
        try:
            ordered_table = ensure_deterministic_order(table)
            yield from stream_ibis(ordered_table, backend, batch_size=batch_size)
            return
        except (AttributeError, Exception):  # pragma: no cover - fallback path
            pass

    if "timestamp" in table.columns:
        table = table.order_by("timestamp")

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
    messages_table: Table,
    search_text: str,
    enrichment_type: str,
    identifier: str,
    enrichment_id_str: str,
) -> dict[str, Any] | None:
    """Create an enrichment row for a given URL or media reference."""
    first_msg = (
        messages_table.filter(messages_table.message.contains(search_text))
        .order_by(messages_table.timestamp)
        .limit(1)
        .execute()
    )

    if len(first_msg) == 0:
        return None

    timestamp = first_msg.iloc[0]["timestamp"]
    enrichment_timestamp = _safe_timestamp_plus_one(timestamp)
    return {
        "timestamp": enrichment_timestamp,
        "date": enrichment_timestamp.date(),
        "author": "egregora",
        "message": f"[{enrichment_type} Enrichment] {identifier}\nEnrichment saved: {enrichment_id_str}",
        "original_line": "",
        "tagged_line": "",
    }


def _process_single_url(
    url: str,
    url_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
) -> tuple[str | None, str]:
    """Process a single URL for enrichment."""
    cache_key = make_enrichment_cache_key(kind="url", identifier=url)

    cache_entry = cache.load(cache_key)
    if cache_entry:
        markdown = cache_entry.get("markdown", "")
    else:
        try:
            markdown = run_url_enrichment(url_agent, url, prompts_dir=prompts_dir)
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
    prompts_dir: Path | None,
) -> tuple[str | None, str, bool]:
    """Process a single media file for enrichment."""
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
            markdown_content = run_media_enrichment(
                media_agent, file_path, mime_hint=media_type, prompts_dir=prompts_dir
            )
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

    doc = Document(
        content=markdown_content,
        type=DocumentType.ENRICHMENT_MEDIA,
        metadata={
            "filename": file_path.name,
            "media_type": media_type,
        },
    )
    context.output_format.serve(doc)
    enrichment_id_str = doc.document_id

    return enrichment_id_str, markdown_content, pii_detected


from .extractors import extract_unique_urls, extract_unique_media_references, _build_media_filename_lookup

def _enrich_urls(
    messages_table: Table,
    url_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    max_enrichments: int,
) -> list[dict[str, Any]]:
    """Enrich unique URLs found in the messages table."""
    new_rows: list[dict[str, Any]] = []
    unique_urls = extract_unique_urls(messages_table, max_enrichments)

    for i, url in enumerate(sorted(unique_urls)):
        if i >= max_enrichments:
            break

        enrichment_id_str, _markdown = _process_single_url(url, url_agent, cache, context, prompts_dir)
        if enrichment_id_str is None:
            continue

        enrichment_row = _create_enrichment_row(messages_table, url, "URL", url, enrichment_id_str)
        if enrichment_row:
            new_rows.append(enrichment_row)

    return new_rows

def _enrich_media(
    messages_table: Table,
    media_mapping: dict[str, Path],
    media_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    max_enrichments: int,
    enrichment_count: int,
) -> tuple[list[dict[str, Any]], int, bool]:
    """Enrich unique media references found in the messages table."""
    new_rows: list[dict[str, Any]] = []
    pii_detected_count = 0
    pii_media_deleted = False

    media_filename_lookup = _build_media_filename_lookup(media_mapping)
    unique_media = extract_unique_media_references(messages_table, media_mapping)

    for ref in sorted(unique_media)[: max_enrichments - enrichment_count]:
        lookup_result = media_filename_lookup.get(ref)
        if not lookup_result:
            continue

        _original_filename, file_path = lookup_result

        enrichment_id_str, _markdown_content, pii_detected = _process_single_media(
            ref, media_filename_lookup, media_agent, cache, context, prompts_dir
        )

        if enrichment_id_str is None:
            continue

        if pii_detected:
            pii_detected_count += 1
            pii_media_deleted = True

        enrichment_row = _create_enrichment_row(
            messages_table, ref, "Media", file_path.name, enrichment_id_str
        )
        if enrichment_row:
            new_rows.append(enrichment_row)

    return new_rows, pii_detected_count, pii_media_deleted


def _replace_pii_media_references(
    messages_table: Table,
    media_mapping: dict[str, Path],
    docs_dir: Path,
    posts_dir: Path,
) -> Table:
    """Replace media references in messages after PII deletion."""

    @ibis.udf.scalar.python
    def replace_media_udf(message: str) -> str:
        return replace_media_mentions(message, media_mapping, docs_dir, posts_dir) if message else message

    return messages_table.mutate(message=replace_media_udf(messages_table.message))


from egregora.database.persistence import combine_with_enrichment_rows, persist_to_duckdb

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

    combined = combine_with_enrichment_rows(messages_table, new_rows)

    duckdb_connection = context.duckdb_connection
    target_table = context.target_table

    if (duckdb_connection is None) != (target_table is None):
        msg = "duckdb_connection and target_table must be provided together when persisting"
        raise ValueError(msg)

    if duckdb_connection and target_table:
        persist_to_duckdb(combined, duckdb_connection, target_table)

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
    "EnrichmentRuntimeContext",
    "MediaEnrichmentJob",
    "UrlEnrichmentJob",
    "_iter_table_record_batches",
    "build_batch_requests",
    "enrich_table",
    "enrich_table_simple",
    "map_batch_results",
]
