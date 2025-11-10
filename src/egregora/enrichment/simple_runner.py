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

from egregora.database.schema import CONVERSATION_SCHEMA
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


def enrich_table_simple(  # noqa: C901, PLR0912, PLR0915
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

    # Create thin agents (created once, reused for all items)
    site_root = context.site_root
    url_agent = make_url_agent(url_model, site_root=site_root) if enable_url else None
    media_agent = make_media_agent(vision_model, site_root=site_root) if enable_media else None

    if messages_table.count().execute() == 0:
        return messages_table

    new_rows: list[dict[str, Any]] = []
    enrichment_count = 0
    pii_detected_count = 0
    pii_media_deleted = False

    # --- URL Enrichment: Extract unique URLs from table ---
    if enable_url and url_agent is not None:
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

            cache_key = make_enrichment_cache_key(kind="url", identifier=url)

            # Check cache first
            cache_entry = cache.load(cache_key)
            if cache_entry:
                markdown = cache_entry.get("markdown", "")
            else:
                # Call agent (one call per URL)
                try:
                    markdown = run_url_enrichment(url_agent, url, site_root=site_root)
                    cache.store(cache_key, {"markdown": markdown, "type": "url"})
                except Exception as exc:  # noqa: BLE001 - log and continue enrichment
                    logger.warning("URL enrichment failed for %s: %s", url, exc)
                    continue

            # Write output file
            enrichment_id = uuid.uuid5(uuid.NAMESPACE_URL, url)
            enrichment_path = docs_dir / "media" / "urls" / f"{enrichment_id}.md"
            _atomic_write_text(enrichment_path, markdown)

            # Add enrichment row (use first message timestamp for simplicity)
            first_msg_with_url = (
                messages_table.filter(messages_table.message.contains(url))
                .order_by(messages_table.timestamp)
                .limit(1)
                .execute()
            )

            if len(first_msg_with_url) > 0:
                timestamp = first_msg_with_url.iloc[0]["timestamp"]
                enrichment_timestamp = _safe_timestamp_plus_one(timestamp)
                new_rows.append(
                    {
                        "timestamp": enrichment_timestamp,
                        "date": enrichment_timestamp.date(),
                        "author": "egregora",
                        "message": f"[URL Enrichment] {url}\nEnrichment saved: {enrichment_path}",
                        "original_line": "",
                        "tagged_line": "",
                    }
                )

            enrichment_count += 1

    # --- Media Enrichment: Extract unique media from table ---
    if enable_media and media_mapping and media_agent is not None:
        # Build media filename lookup
        media_filename_lookup: dict[str, tuple[str, Path]] = {}
        for original_filename, file_path in media_mapping.items():
            media_filename_lookup[original_filename] = (original_filename, file_path)
            media_filename_lookup[file_path.name] = (original_filename, file_path)

        # Get messages with media references
        media_messages = messages_table.filter(messages_table.message.notnull()).execute()
        unique_media: set[str] = set()

        for row in media_messages.itertuples():
            if enrichment_count >= max_enrichments:
                break

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

        # Process each unique media file
        for ref in sorted(unique_media)[: max_enrichments - enrichment_count]:
            lookup_result = media_filename_lookup.get(ref)
            if not lookup_result:
                continue

            original_filename, file_path = lookup_result
            cache_key = make_enrichment_cache_key(kind="media", identifier=str(file_path))

            media_type = detect_media_type(file_path)
            if not media_type:
                logger.warning("Unsupported media type for enrichment: %s", file_path.name)
                continue

            # Check cache first
            cache_entry = cache.load(cache_key)
            if cache_entry:
                markdown_content = cache_entry.get("markdown", "")
            else:
                # Call agent
                try:
                    markdown_content = run_media_enrichment(
                        media_agent, file_path, mime_hint=media_type, site_root=site_root
                    )
                    cache.store(cache_key, {"markdown": markdown_content, "type": "media"})
                except Exception as exc:  # noqa: BLE001 - skip and continue pipeline
                    logger.warning("Media enrichment failed for %s (%s): %s", file_path, media_type, exc)
                    continue

            # Check for PII detection
            if "PII_DETECTED" in markdown_content:
                logger.warning("PII detected in media: %s. Media will be deleted.", file_path.name)
                markdown_content = markdown_content.replace("PII_DETECTED", "").strip()
                try:
                    file_path.unlink()
                    logger.info("Deleted media file containing PII: %s", file_path)
                    pii_media_deleted = True
                    pii_detected_count += 1
                except (FileNotFoundError, PermissionError):
                    logger.exception("Failed to delete %s", file_path)
                except OSError:
                    logger.exception("Unexpected OS error deleting %s", file_path)

            if not markdown_content:
                markdown_content = f"[No enrichment generated for media: {file_path.name}]"

            # Write output file
            enrichment_path = file_path.with_suffix(file_path.suffix + ".md")
            _atomic_write_text(enrichment_path, markdown_content)

            # Add enrichment row (use first message timestamp)
            # Note: ref might be original filename or UUID filename
            first_msg_with_media = (
                messages_table.filter(messages_table.message.contains(ref))
                .order_by(messages_table.timestamp)
                .limit(1)
                .execute()
            )

            if len(first_msg_with_media) > 0:
                timestamp = first_msg_with_media.iloc[0]["timestamp"]
                enrichment_timestamp = _safe_timestamp_plus_one(timestamp)
                new_rows.append(
                    {
                        "timestamp": enrichment_timestamp,
                        "date": enrichment_timestamp.date(),
                        "author": "egregora",
                        "message": f"[Media Enrichment] {file_path.name}\nEnrichment saved: {enrichment_path}",
                        "original_line": "",
                        "tagged_line": "",
                    }
                )

            enrichment_count += 1

    # If PII was deleted, update media references in messages
    if pii_media_deleted:

        @ibis.udf.scalar.python
        def replace_media_udf(message: str) -> str:
            return replace_media_mentions(message, media_mapping, docs_dir, posts_dir) if message else message

        messages_table = messages_table.mutate(message=replace_media_udf(messages_table.message))

    # Create combined table (with or without enrichments)
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

    # Persist to DuckDB if connection and table name provided
    duckdb_connection = context.duckdb_connection
    target_table = context.target_table

    if (duckdb_connection is None) != (target_table is None):
        msg = "duckdb_connection and target_table must be provided together when persisting"
        raise ValueError(msg)

    if duckdb_connection and target_table:
        from egregora import database  # noqa: PLC0415 - avoid circular import

        if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", target_table):
            msg = "target_table must be a valid DuckDB identifier"
            raise ValueError(msg)

        database.schema.create_table_if_not_exists(duckdb_connection, target_table, CONVERSATION_SCHEMA)
        quoted_table = database.schema.quote_identifier(target_table)
        column_list = ", ".join(database.schema.quote_identifier(col) for col in CONVERSATION_SCHEMA.names)
        temp_view = f"_egregora_enrichment_{uuid.uuid4().hex}"

        try:
            duckdb_connection.create_view(temp_view, combined, overwrite=True)
            quoted_view = database.schema.quote_identifier(temp_view)
            duckdb_connection.raw_sql("BEGIN TRANSACTION")
            try:
                duckdb_connection.raw_sql(f"DELETE FROM {quoted_table}")
                duckdb_connection.raw_sql(
                    f"INSERT INTO {quoted_table} ({column_list}) SELECT {column_list} FROM {quoted_view}"
                )
                duckdb_connection.raw_sql("COMMIT")
            except Exception:
                duckdb_connection.raw_sql("ROLLBACK")
                raise
        finally:
            duckdb_connection.drop_view(temp_view, force=True)

    if pii_detected_count > 0:
        logger.info("Privacy summary: %d media file(s) deleted due to PII detection", pii_detected_count)

    return combined
