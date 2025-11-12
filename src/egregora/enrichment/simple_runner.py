"""Simple straight-loop enrichment runner - no batches, no jobs, just a for-loop.

This module implements the enrichment runner using the thin-agent pattern:
- Iterate through rows
- For each URL/media reference, check cache
- If not cached, call agent (one call per item)
- Write output files
- Return enriched table

Usage:
    enriched_table = enrich_table_simple(
        messages_table=table,
        media_mapping=media_mapping,
        config=config,
        context=context,
    )
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
from ibis.expr.types import Table

from egregora.core.document import Document, DocumentType
from egregora.database.schemas import CONVERSATION_SCHEMA
from egregora.enrichment.batch import _safe_timestamp_plus_one
from egregora.enrichment.media import (
    detect_media_type,
    extract_urls,
    find_media_references,
    replace_media_mentions,
)
from egregora.enrichment.thin_agents import (
    make_media_agent,
    make_url_agent,
    run_media_enrichment,
    run_url_enrichment,
)
from egregora.utils import make_enrichment_cache_key

if TYPE_CHECKING:
    from egregora.config.schema import EgregoraConfig
    from egregora.enrichment.core import EnrichmentRuntimeContext
    from egregora.utils.cache import EnrichmentCache

logger = logging.getLogger(__name__)


def _atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text to a file atomically to prevent partial writes during concurrent runs.

    Writes to a temporary file in the same directory, then atomically renames it.
    This ensures readers never see partial/incomplete content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)

        # Atomic rename (replaces destination if it exists)
        Path(temp_path).replace(path)
    except OSError as e:
        try:
            Path(temp_path).unlink()
        except (FileNotFoundError, PermissionError):
            pass
        except OSError as cleanup_error:
            logger.warning("Failed to cleanup temp file %s: %s", temp_path, cleanup_error)
        raise e from None


@dataclass
class SimpleEnrichmentResult:
    """Result of simple enrichment run."""

    new_rows: list[dict[str, Any]]
    pii_detected_count: int = 0
    pii_media_deleted: bool = False


def _create_enrichment_row(
    messages_table: Table,
    search_text: str,
    enrichment_type: str,
    identifier: str,
    enrichment_id_str: str,
) -> dict[str, Any] | None:
    """Create an enrichment row for a given URL or media reference.

    Args:
        messages_table: Table to search for the first message containing the reference
        search_text: Text to search for in messages (URL or media filename)
        enrichment_type: Type of enrichment ("URL" or "Media")
        identifier: Display identifier (URL or filename)
        enrichment_id_str: Enrichment ID string

    Returns:
        Dict representing the enrichment row, or None if no matching message found

    """
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


def _serve_enrichment_document(
    document: Document,
    context: "EnrichmentRuntimeContext",
    *,
    source_url: str | None = None,
    media_path: Path | None = None,
) -> None:
    """Persist an enrichment document using legacy or modern output formats.

    The enrichment pipeline is being migrated from the legacy MkDocs coordinator
    (which exposes ``enrichments.write_*`` helpers) to the new OutputFormat
    ``serve()`` API. During the transition, the pipeline may receive either
    implementation. This helper detects the available interface and performs the
    appropriate persistence call, ensuring backwards compatibility.

    Args:
        document: Document to persist.
        context: Runtime context containing the output format instance.
        source_url: Original URL for URL enrichments (legacy API requirement).
        media_path: Absolute path to the media file for media enrichments.

    Raises:
        AttributeError: If the output format exposes neither ``serve`` nor
            ``enrichments`` helpers.
        ValueError: If required contextual information is missing for the
            legacy persistence helpers.
    """

    output_format = context.output_format
    serve_fn = getattr(output_format, "serve", None)
    if callable(serve_fn):
        serve_fn(document)
        return

    enrichments = getattr(output_format, "enrichments", None)
    if enrichments is None:
        msg = (
            "Output format does not implement 'serve' or legacy enrichment helpers; "
            "cannot persist enrichment document"
        )
        raise AttributeError(msg)

    if document.type == DocumentType.ENRICHMENT_URL:
        if source_url is None:
            raise ValueError("source_url is required for legacy URL enrichment writes")
        enrichments.write_url_enrichment(source_url, document.content)
        return

    if document.type == DocumentType.ENRICHMENT_MEDIA:
        if media_path is None:
            raise ValueError("media_path is required for legacy media enrichment writes")

        # Legacy API expects a path relative to the site root. Fall back to the
        # filename if we cannot make it relative (e.g., when site_root is None).
        relative_path: str
        if isinstance(media_path, Path):
            candidate = media_path
        else:
            candidate = Path(media_path)

        if candidate.is_absolute() and context.site_root is not None:
            try:
                relative_path = str(candidate.relative_to(context.site_root))
            except ValueError:
                relative_path = candidate.name
        else:
            relative_path = str(candidate)

        enrichments.write_media_enrichment(relative_path, document.content)
        return

    raise ValueError(f"Unsupported document type for enrichment persistence: {document.type}")


def _process_single_url(
    url: str,
    url_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
) -> tuple[str | None, str]:
    """Process a single URL for enrichment.

    Args:
        url: URL to enrich
        url_agent: Pydantic AI agent for URL enrichment
        cache: Enrichment cache
        context: Runtime context
        prompts_dir: Optional custom prompts directory

    Returns:
        Tuple of (enrichment_id_str or None, markdown_content)

    """
    cache_key = make_enrichment_cache_key(kind="url", identifier=url)

    # Check cache first
    cache_entry = cache.load(cache_key)
    if cache_entry:
        markdown = cache_entry.get("markdown", "")
    else:
        # Call agent (one call per URL)
        try:
            markdown = run_url_enrichment(url_agent, url, prompts_dir=prompts_dir)
            cache.store(cache_key, {"markdown": markdown, "type": "url"})
        except Exception:
            logger.exception("URL enrichment failed for %s", url)
            return None, ""

    # Create Document and serve using OutputFormat protocol
    doc = Document(
        content=markdown,
        type=DocumentType.ENRICHMENT_URL,
        metadata={"url": url},
    )
    _serve_enrichment_document(doc, context, source_url=url)
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
    """Process a single media file for enrichment.

    Args:
        ref: Media reference (filename or UUID)
        media_filename_lookup: Lookup dict mapping refs to (original_filename, file_path)
        media_agent: Pydantic AI agent for media enrichment
        cache: Enrichment cache
        context: Runtime context
        prompts_dir: Optional custom prompts directory

    Returns:
        Tuple of (enrichment_id_str or None, markdown_content, pii_detected)

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

    # Check cache first
    cache_entry = cache.load(cache_key)
    if cache_entry:
        markdown_content = cache_entry.get("markdown", "")
    else:
        # Call agent
        try:
            markdown_content = run_media_enrichment(
                media_agent, file_path, mime_hint=media_type, prompts_dir=prompts_dir
            )
            cache.store(cache_key, {"markdown": markdown_content, "type": "media"})
        except Exception:
            logger.exception("Media enrichment failed for %s (%s)", file_path, media_type)
            return None, "", False

    # Check for PII detection
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

    # Create Document and serve using OutputFormat protocol
    # OutputFormat will determine storage location from filename + type
    doc = Document(
        content=markdown_content,
        type=DocumentType.ENRICHMENT_MEDIA,
        metadata={
            "filename": file_path.name,
            "media_type": media_type,
        },
    )
    _serve_enrichment_document(doc, context, media_path=file_path)
    enrichment_id_str = doc.document_id

    return enrichment_id_str, markdown_content, pii_detected


def _enrich_urls(
    messages_table: Table,
    url_agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    max_enrichments: int,
) -> list[dict[str, Any]]:
    """Extract and enrich URLs from messages table.

    Args:
        messages_table: Table with messages to enrich
        url_agent: Pydantic AI agent for URL enrichment
        cache: Enrichment cache
        context: Runtime context
        prompts_dir: Optional custom prompts directory
        max_enrichments: Maximum number of enrichments to process

    Returns:
        List of enrichment row dicts

    """
    new_rows: list[dict[str, Any]] = []
    enrichment_count = 0

    # Get messages with URLs (use Python for URL extraction since regex in SQL is complex)
    url_messages = messages_table.filter(messages_table.message.notnull()).execute()
    unique_urls: set[str] = set()

    for row in url_messages.itertuples():
        if enrichment_count >= max_enrichments:
            break
        urls = extract_urls(row.message)
        for url in urls[:3]:  # Limit URLs per message
            if enrichment_count >= max_enrichments:
                break
            unique_urls.add(url)

    # Process each unique URL
    for url in sorted(unique_urls)[:max_enrichments]:
        if enrichment_count >= max_enrichments:
            break

        enrichment_id_str, _markdown = _process_single_url(url, url_agent, cache, context, prompts_dir)
        if enrichment_id_str is None:
            continue

        # Add enrichment row
        enrichment_row = _create_enrichment_row(messages_table, url, "URL", url, enrichment_id_str)
        if enrichment_row:
            new_rows.append(enrichment_row)

        enrichment_count += 1

    return new_rows


def _build_media_filename_lookup(media_mapping: dict[str, Path]) -> dict[str, tuple[str, Path]]:
    """Build a lookup dict mapping media filenames to (original_filename, file_path).

    Args:
        media_mapping: Mapping of original filenames to file paths

    Returns:
        Dict mapping both original and UUID filenames to (original_filename, file_path)

    """
    lookup: dict[str, tuple[str, Path]] = {}
    for original_filename, file_path in media_mapping.items():
        lookup[original_filename] = (original_filename, file_path)
        lookup[file_path.name] = (original_filename, file_path)
    return lookup


def _extract_media_references(
    messages_table: Table, media_filename_lookup: dict[str, tuple[str, Path]]
) -> set[str]:
    """Extract unique media references from messages table.

    Args:
        messages_table: Table with messages to scan
        media_filename_lookup: Lookup dict for validating media references

    Returns:
        Set of unique media references found in messages

    """
    media_messages = messages_table.filter(messages_table.message.notnull()).execute()
    unique_media: set[str] = set()

    for row in media_messages.itertuples():
        # Extract all media references
        refs = find_media_references(row.message)
        markdown_refs = re.findall("!\\[[^\\]]*\\]\\([^)]*?([a-f0-9\\-]+\\.\\w+)\\)", row.message)
        uuid_refs = re.findall(
            "\\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\\.\\w+)", row.message
        )
        refs.extend(markdown_refs)
        refs.extend(uuid_refs)

        # Add to unique set if in media_mapping
        for ref in set(refs):
            if ref in media_filename_lookup:
                unique_media.add(ref)

    return unique_media


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
    """Extract and enrich media from messages table.

    Args:
        messages_table: Table with messages to enrich
        media_mapping: Mapping of media filenames to file paths
        media_agent: Pydantic AI agent for media enrichment
        cache: Enrichment cache
        context: Runtime context
        prompts_dir: Optional custom prompts directory
        max_enrichments: Maximum number of enrichments to process
        enrichment_count: Current enrichment count (from URL enrichment)

    Returns:
        Tuple of (enrichment_rows, pii_detected_count, pii_media_deleted)

    """
    new_rows: list[dict[str, Any]] = []
    pii_detected_count = 0
    pii_media_deleted = False

    # Build media filename lookup
    media_filename_lookup = _build_media_filename_lookup(media_mapping)

    # Extract unique media references
    unique_media = _extract_media_references(messages_table, media_filename_lookup)

    # Process each unique media file
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

        # Add enrichment row
        enrichment_row = _create_enrichment_row(
            messages_table, ref, "Media", file_path.name, enrichment_id_str
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
    """Replace media references in messages after PII deletion.

    Args:
        messages_table: Table with messages
        media_mapping: Mapping of media filenames to file paths
        docs_dir: Docs directory path
        posts_dir: Posts directory path

    Returns:
        Updated table with media references replaced

    """

    @ibis.udf.scalar.python
    def replace_media_udf(message: str) -> str:
        return replace_media_mentions(message, media_mapping, docs_dir, posts_dir) if message else message

    return messages_table.mutate(message=replace_media_udf(messages_table.message))


def _combine_enrichment_tables(
    messages_table: Table,
    new_rows: list[dict[str, Any]],
) -> Table:
    """Combine messages table with enrichment rows.

    Args:
        messages_table: Original messages table
        new_rows: List of enrichment row dicts

    Returns:
        Combined table with enrichments added and sorted by timestamp

    """
    schema = CONVERSATION_SCHEMA
    messages_table_filtered = messages_table.select(*schema.names)
    messages_table_filtered = messages_table_filtered.mutate(
        timestamp=messages_table_filtered.timestamp.cast("timestamp('UTC', 9)")
    ).cast(schema)

    if new_rows:
        # Add enrichment rows if we have any
        normalized_rows = [{column: row.get(column) for column in schema.names} for row in new_rows]
        enrichment_table = ibis.memtable(normalized_rows).cast(schema)
        combined = messages_table_filtered.union(enrichment_table, distinct=False)
        combined = combined.order_by("timestamp")
    else:
        # No enrichments, just use filtered messages table
        combined = messages_table_filtered

    return combined


def _persist_to_duckdb(
    combined: Table,
    duckdb_connection: Any,
    target_table: str,
) -> None:
    """Persist enriched table to DuckDB.

    Args:
        combined: Combined table with enrichments
        duckdb_connection: DuckDB connection
        target_table: Target table name

    """
    from egregora.database import schemas

    if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", target_table):
        msg = "target_table must be a valid DuckDB identifier"
        raise ValueError(msg)

    schemas.create_table_if_not_exists(duckdb_connection, target_table, CONVERSATION_SCHEMA)
    quoted_table = schemas.quote_identifier(target_table)
    column_list = ", ".join(schemas.quote_identifier(col) for col in CONVERSATION_SCHEMA.names)
    temp_view = f"_egregora_enrichment_{uuid.uuid4().hex}"

    try:
        duckdb_connection.create_view(temp_view, combined, overwrite=True)
        quoted_view = schemas.quote_identifier(temp_view)
        duckdb_connection.raw_sql("BEGIN TRANSACTION")
        try:
            duckdb_connection.raw_sql(f"DELETE FROM {quoted_table}")  # nosec B608 - quoted_table uses quote_identifier (line 501)
            duckdb_connection.raw_sql(
                f"INSERT INTO {quoted_table} ({column_list}) SELECT {column_list} FROM {quoted_view}"  # nosec B608 - all identifiers quoted (lines 501-502, 507)
            )
            duckdb_connection.raw_sql("COMMIT")
        except Exception:
            logger.exception("Transaction failed during DuckDB persistence, rolling back")
            duckdb_connection.raw_sql("ROLLBACK")
            raise
    finally:
        duckdb_connection.drop_view(temp_view, force=True)


def enrich_table_simple(
    messages_table: Table,
    media_mapping: dict[str, Path],
    config: EgregoraConfig,
    context: EnrichmentRuntimeContext,
) -> Table:
    """Add LLM-generated enrichment rows using thin-agent pattern.

    Uses Ibis/SQL to extract URLs and media references, then processes unique items.

    Args:
        messages_table: Table with messages to enrich
        media_mapping: Mapping of media filenames to file paths
        config: Egregora configuration (models, enrichment settings)
        context: Runtime context (cache, paths, DB connection)

    Returns:
        Table with enrichment rows added

    """
    # Extract config/context values
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

    # Derive prompts_dir for custom Jinja template overrides
    prompts_dir = context.site_root / ".egregora" / "prompts" if context.site_root else None

    # Create thin agents (created once, reused for all items)
    url_agent = make_url_agent(url_model, prompts_dir=prompts_dir) if enable_url else None
    media_agent = make_media_agent(vision_model, prompts_dir=prompts_dir) if enable_media else None

    if messages_table.count().execute() == 0:
        return messages_table

    # Track all enrichment rows and PII detection
    new_rows: list[dict[str, Any]] = []
    pii_detected_count = 0
    pii_media_deleted = False

    # --- URL Enrichment ---
    if enable_url and url_agent is not None:
        url_rows = _enrich_urls(messages_table, url_agent, cache, context, prompts_dir, max_enrichments)
        new_rows.extend(url_rows)

    # --- Media Enrichment ---
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

    # --- Replace PII media references if needed ---
    if pii_media_deleted:
        messages_table = _replace_pii_media_references(messages_table, media_mapping, docs_dir, posts_dir)

    # --- Combine tables ---
    combined = _combine_enrichment_tables(messages_table, new_rows)

    # --- Persist to DuckDB if configured ---
    duckdb_connection = context.duckdb_connection
    target_table = context.target_table

    if (duckdb_connection is None) != (target_table is None):
        msg = "duckdb_connection and target_table must be provided together when persisting"
        raise ValueError(msg)

    if duckdb_connection and target_table:
        _persist_to_duckdb(combined, duckdb_connection, target_table)

    # --- Log PII summary ---
    if pii_detected_count > 0:
        logger.info("Privacy summary: %d media file(s) deleted due to PII detection", pii_detected_count)

    return combined
