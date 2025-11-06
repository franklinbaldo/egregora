"""Simple enrichment: extract media, add LLM-described context as table rows.

Enrichment adds context for URLs and media as new table rows with author 'egregora'.
The LLM sees enrichment context inline with original messages.

Documentation:
- Architecture (Enricher): docs/guides/architecture.md#4-enricher-enricherpy
- Core Concepts: docs/getting-started/concepts.md#4-enrich-optional

MODERN (Phase 2): Uses EnrichmentRuntimeContext to reduce parameters.
"""

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

from egregora.config.schema import EgregoraConfig
from egregora.database import schema as database_schema
from egregora.database.schema import CONVERSATION_SCHEMA
from egregora.enrichment.agents import (
    MediaEnrichmentContext,
    UrlEnrichmentContext,
    create_media_enrichment_agent,
    create_url_enrichment_agent,
    load_file_as_binary_content,
)
from egregora.enrichment.batch import (
    MediaEnrichmentJob,
    UrlEnrichmentJob,
    _ensure_datetime,
    _safe_timestamp_plus_one,
    _table_to_pylist,
)
from egregora.enrichment.media import (
    detect_media_type,
    extract_urls,
    find_media_references,
    replace_media_mentions,
)
from egregora.utils import EnrichmentCache, make_enrichment_cache_key

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend
else:
    DuckDBBackend = Any


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


if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend
else:
    DuckDBBackend = Any


@dataclass(frozen=True, slots=True)
class EnrichmentRuntimeContext:
    """Runtime context for enrichment execution.

    MODERN (Phase 2): Bundles runtime parameters to reduce function signatures.
    Separates runtime data (paths, cache, DB) from configuration (EgregoraConfig).
    """

    cache: EnrichmentCache
    docs_dir: Path
    posts_dir: Path
    duckdb_connection: "DuckDBBackend | None" = None
    target_table: str | None = None


def enrich_table(
    messages_table: Table,
    media_mapping: dict[str, Path],
    config: EgregoraConfig,
    context: EnrichmentRuntimeContext,
) -> Table:
    """Add LLM-generated enrichment rows to Table for URLs and media.

    MODERN (Phase 2): Reduced from 13 parameters to 4 (table, media_mapping, config, context).

    Args:
        messages_table: Table with messages to enrich
        media_mapping: Mapping of media filenames to file paths
        config: Egregora configuration (models, enrichment settings)
        context: Runtime context (cache, paths, DB connection)

    Returns:
        Table with enrichment rows added

    """
    # Extract values from config and context (Phase 2)
    url_model = config.models.enricher
    vision_model = config.models.enricher_vision
    max_enrichments = config.enrichment.max_enrichments
    enable_url = config.enrichment.enable_url
    enable_media = config.enrichment.enable_media
    cache = context.cache
    docs_dir = context.docs_dir
    posts_dir = context.posts_dir
    duckdb_connection = context.duckdb_connection
    target_table = context.target_table
    logger.info("[blue]🌐 Enricher text model:[/] %s", url_model)
    logger.info("[blue]🖼️  Enricher vision model:[/] %s", vision_model)
    url_enrichment_agent = create_url_enrichment_agent(url_model)
    media_enrichment_agent = create_media_enrichment_agent(vision_model)
    if messages_table.count().execute() == 0:
        return messages_table
    rows = _table_to_pylist(messages_table)
    new_rows: list[dict[str, Any]] = []
    enrichment_count = 0
    pii_detected_count = 0
    pii_media_deleted = False
    seen_url_keys: set[str] = set()
    seen_media_keys: set[str] = set()
    url_jobs: list[UrlEnrichmentJob] = []
    media_jobs: list[MediaEnrichmentJob] = []
    media_filename_lookup: dict[str, tuple[str, Path]] = {}
    if enable_media and media_mapping:
        for original_filename, file_path in media_mapping.items():
            media_filename_lookup[original_filename] = (original_filename, file_path)
            media_filename_lookup[file_path.name] = (original_filename, file_path)
    for row in rows:
        if enrichment_count >= max_enrichments:
            break
        message = row.get("message", "")
        timestamp = row["timestamp"]
        author = row.get("author", "unknown")
        if enable_url and message:
            urls = extract_urls(message)
            for url in urls[:3]:
                if enrichment_count >= max_enrichments:
                    break
                cache_key = make_enrichment_cache_key(kind="url", identifier=url)
                if cache_key in seen_url_keys:
                    continue
                enrichment_id = uuid.uuid5(uuid.NAMESPACE_URL, url)
                enrichment_path = docs_dir / "media" / "urls" / f"{enrichment_id}.md"
                url_job = UrlEnrichmentJob(
                    key=cache_key,
                    url=url,
                    original_message=message,
                    sender_uuid=author,
                    timestamp=timestamp,
                    path=enrichment_path,
                    tag=f"url:{cache_key}",
                )
                cache_entry = cache.load(cache_key)
                if cache_entry:
                    url_job.markdown = cache_entry.get("markdown")
                    url_job.cached = True
                url_jobs.append(url_job)
                seen_url_keys.add(cache_key)
                enrichment_count += 1
        if enable_media and media_filename_lookup and message:
            media_refs = find_media_references(message)
            markdown_media_pattern = "!\\[[^\\]]*\\]\\([^)]*?([a-f0-9\\-]+\\.\\w+)\\)"
            markdown_matches = re.findall(markdown_media_pattern, message)
            media_refs.extend(markdown_matches)
            uuid_filename_pattern = "\\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\\.\\w+)"
            uuid_matches = re.findall(uuid_filename_pattern, message)
            media_refs.extend(uuid_matches)
            media_refs = [ref for ref in set(media_refs) if ref in media_filename_lookup]
            for ref in media_refs:
                if enrichment_count >= max_enrichments:
                    break
                lookup_result = media_filename_lookup.get(ref)
                if not lookup_result:
                    continue
                original_filename, file_path = lookup_result
                cache_key = make_enrichment_cache_key(kind="media", identifier=str(file_path))
                if cache_key in seen_media_keys:
                    continue
                media_type = detect_media_type(file_path)
                if not media_type:
                    logger.warning("Unsupported media type for enrichment: %s", file_path.name)
                    continue
                enrichment_path = file_path.with_suffix(file_path.suffix + ".md")
                media_job = MediaEnrichmentJob(
                    key=cache_key,
                    original_filename=original_filename,
                    file_path=file_path,
                    original_message=message,
                    sender_uuid=author,
                    timestamp=timestamp,
                    path=enrichment_path,
                    tag=f"media:{cache_key}",
                    media_type=media_type,
                )
                cache_entry = cache.load(cache_key)
                if cache_entry:
                    media_job.markdown = cache_entry.get("markdown")
                    media_job.cached = True
                media_jobs.append(media_job)
                seen_media_keys.add(cache_key)
                enrichment_count += 1
    pending_url_jobs = [url_job for url_job in url_jobs if url_job.markdown is None]
    if pending_url_jobs:
        for url_job in pending_url_jobs:
            ts = _ensure_datetime(url_job.timestamp)
            context = UrlEnrichmentContext(
                url=url_job.url,
                original_message=url_job.original_message,
                sender_uuid=url_job.sender_uuid,
                date=ts.strftime("%Y-%m-%d"),
                time=ts.strftime("%H:%M"),
            )
            result = url_enrichment_agent.run_sync("Enrich this URL", deps=context)
            url_job.markdown = result.data.markdown
            cache.store(url_job.key, {"markdown": result.data.markdown, "type": "url"})
    pending_media_jobs = [job for job in media_jobs if job.markdown is None]
    if pending_media_jobs:
        for media_job in pending_media_jobs:
            binary_content = load_file_as_binary_content(media_job.file_path)
            ts = _ensure_datetime(media_job.timestamp)
            try:
                media_path = media_job.file_path.relative_to(docs_dir)
            except ValueError:
                media_path = media_job.file_path
            context = MediaEnrichmentContext(
                media_type=media_job.media_type or "unknown",
                media_filename=media_job.file_path.name,
                media_path=str(media_path),
                original_message=media_job.original_message,
                sender_uuid=media_job.sender_uuid,
                date=ts.strftime("%Y-%m-%d"),
                time=ts.strftime("%H:%M"),
            )
            message_content = [
                "Analyze and enrich this media file. Provide a detailed description in markdown format.",
                binary_content,
            ]
            result = media_enrichment_agent.run_sync(message_content, deps=context)
            markdown_content = result.data.markdown.strip()
            if not markdown_content:
                markdown_content = f"[No enrichment generated for media: {media_job.file_path.name}]"
            if "PII_DETECTED" in markdown_content:
                logger.warning(
                    "PII detected in media: %s. Media will be deleted after redaction.",
                    media_job.file_path.name,
                )
                markdown_content = markdown_content.replace("PII_DETECTED", "").strip()
                try:
                    media_job.file_path.unlink()
                    logger.info("Deleted media file containing PII: %s", media_job.file_path)
                    pii_media_deleted = True
                    pii_detected_count += 1
                except (FileNotFoundError, PermissionError) as delete_error:
                    logger.exception("Failed to delete %s: %s", media_job.file_path, delete_error)
                except OSError as delete_error:
                    logger.exception("Unexpected OS error deleting %s: %s", media_job.file_path, delete_error)
            media_job.markdown = markdown_content
            cache.store(media_job.key, {"markdown": markdown_content, "type": "media"})
    for url_job in url_jobs:
        if not url_job.markdown:
            continue
        _atomic_write_text(url_job.path, url_job.markdown)
        enrichment_timestamp = _safe_timestamp_plus_one(url_job.timestamp)
        new_rows.append(
            {
                "timestamp": enrichment_timestamp,
                "date": enrichment_timestamp.date(),
                "author": "egregora",
                "message": f"[URL Enrichment] {url_job.url}\nEnrichment saved: {url_job.path}",
                "original_line": "",
                "tagged_line": "",
            }
        )
    for media_job in media_jobs:
        if not media_job.markdown:
            continue
        _atomic_write_text(media_job.path, media_job.markdown)
        enrichment_timestamp = _safe_timestamp_plus_one(media_job.timestamp)
        new_rows.append(
            {
                "timestamp": enrichment_timestamp,
                "date": enrichment_timestamp.date(),
                "author": "egregora",
                "message": f"[Media Enrichment] {media_job.file_path.name}\nEnrichment saved: {media_job.path}",
                "original_line": "",
                "tagged_line": "",
            }
        )
    if pii_media_deleted:

        @ibis.udf.scalar.python
        def replace_media_udf(message: str) -> str:
            return replace_media_mentions(message, media_mapping, docs_dir, posts_dir) if message else message

        messages_table = messages_table.mutate(message=replace_media_udf(messages_table.message))
    if not new_rows:
        return messages_table
    schema = CONVERSATION_SCHEMA
    normalized_rows = [{column: row.get(column) for column in schema.names} for row in new_rows]
    enrichment_table = ibis.memtable(normalized_rows, schema=schema)
    messages_table_filtered = messages_table.select(*schema.names)
    messages_table_filtered = messages_table_filtered.mutate(
        timestamp=messages_table_filtered.timestamp.cast("timestamp('UTC', 9)")
    )
    combined = messages_table_filtered.union(enrichment_table, distinct=False)
    combined = combined.order_by("timestamp")
    if (duckdb_connection is None) != (target_table is None):
        msg = "duckdb_connection and target_table must be provided together when persisting"
        raise ValueError(msg)
    if duckdb_connection and target_table:
        if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", target_table):
            msg = "target_table must be a valid DuckDB identifier"
            raise ValueError(msg)
        database_schema.create_table_if_not_exists(duckdb_connection, target_table, CONVERSATION_SCHEMA)
        quoted_table = database_schema.quote_identifier(target_table)
        column_list = ", ".join(database_schema.quote_identifier(col) for col in CONVERSATION_SCHEMA.names)
        temp_view = f"_egregora_enrichment_{uuid.uuid4().hex}"
        try:
            duckdb_connection.create_view(temp_view, combined, overwrite=True)
            quoted_view = database_schema.quote_identifier(temp_view)
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
