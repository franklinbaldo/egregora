"""Simple enrichment: extract media, add LLM-described context as table rows.

Enrichment adds context for URLs and media as new table rows with author 'egregora'.
The LLM sees enrichment context inline with original messages.

Documentation:
- Architecture (Enricher): docs/guides/architecture.md#4-enricher-enricherpy
- Core Concepts: docs/getting-started/concepts.md#4-enrich-optional
"""

import logging
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import ibis
from ibis.expr.types import Table

from ...config import ModelConfig
from ...core import database_schema
from ...core.database_schema import CONVERSATION_SCHEMA
from ...prompt_templates import (
    DetailedMediaEnrichmentPromptTemplate,
    DetailedUrlEnrichmentPromptTemplate,
)
from ...utils import EnrichmentCache, GeminiBatchClient, make_enrichment_cache_key
from ...utils.batch import BatchPromptResult
from .batch import (
    MediaEnrichmentJob,
    UrlEnrichmentJob,
    _ensure_datetime,
    _safe_timestamp_plus_one,
    _table_to_pylist,
    build_batch_requests,
    map_batch_results,
)
from .media import (
    detect_media_type,
    extract_urls,
    find_media_references,
    replace_media_mentions,
)

logger = logging.getLogger(__name__)


def _atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text to a file atomically to prevent partial writes during concurrent runs.

    Writes to a temporary file in the same directory, then atomically renames it.
    This ensures readers never see partial/incomplete content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory for atomic rename (must be same filesystem)
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        # Write content to temp file
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)

        # Atomic rename (replaces destination if it exists)
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend
else:  # pragma: no cover - duckdb backend available at runtime when installed
    DuckDBBackend = Any


def enrich_table(
    messages_table: Table,
    media_mapping: dict[str, Path],
    text_batch_client: GeminiBatchClient,
    vision_batch_client: GeminiBatchClient,
    cache: EnrichmentCache,
    docs_dir: Path,
    posts_dir: Path,
    model_config: ModelConfig | None = None,
    enable_url: bool = True,
    enable_media: bool = True,
    max_enrichments: int = 50,
    persist_connection: duckdb.DuckDBPyConnection | None = None,
    persist_table: str | None = None,
    *,
    duckdb_connection: "DuckDBBackend | None" = None,
    target_table: str | None = None,
) -> Table:
    """Add LLM-generated enrichment rows to Table for URLs and media."""
    if model_config is None:
        model_config = ModelConfig()

    url_model = model_config.get_model("enricher")
    vision_model = model_config.get_model("enricher_vision")
    logger.info("[blue]🌐 Enricher text model:[/] %s", url_model)
    logger.info("[blue]🖼️  Enricher vision model:[/] %s", vision_model)

    if messages_table.count().execute() == 0:
        return messages_table

    # Use streaming helper to avoid loading entire table into memory
    rows = _table_to_pylist(messages_table)
    new_rows: list[dict[str, Any]] = []
    enrichment_count = 0
    pii_detected_count = 0
    pii_media_deleted = False
    seen_url_keys: set[str] = set()
    seen_media_keys: set[str] = set()

    url_jobs: list[UrlEnrichmentJob] = []
    media_jobs: list[MediaEnrichmentJob] = []

    # Build reverse lookup: filename -> (original_filename, file_path)
    # This avoids O(n×m) substring matching in the hot path
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
            # Extract media references efficiently:
            # 1. WhatsApp-style references (original filenames)
            media_refs = find_media_references(message)

            # 2. UUID-based filenames in markdown links (after media replacement)
            # Pattern: extract filenames from markdown links like ![Image](media/images/uuid.jpg)
            markdown_media_pattern = r"!\[[^\]]*\]\([^)]*?([a-f0-9\-]+\.\w+)\)"
            markdown_matches = re.findall(markdown_media_pattern, message)
            media_refs.extend(markdown_matches)

            # Also check for direct UUID-based filenames (without path)
            uuid_filename_pattern = r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.\w+)\b"
            uuid_matches = re.findall(uuid_filename_pattern, message)
            media_refs.extend(uuid_matches)

            # Deduplicate and only keep refs that exist in our lookup
            media_refs = [ref for ref in set(media_refs) if ref in media_filename_lookup]

            for ref in media_refs:
                if enrichment_count >= max_enrichments:
                    break

                # Look up the file in our hash table (O(1) instead of O(m))
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

                enrichment_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(file_path))
                enrichment_path = docs_dir / "media" / "enrichments" / f"{enrichment_id}.md"
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
        url_records = []
        for url_job in pending_url_jobs:
            ts = _ensure_datetime(url_job.timestamp)
            prompt = DetailedUrlEnrichmentPromptTemplate(
                url=url_job.url,
                original_message=url_job.original_message,
                sender_uuid=url_job.sender_uuid,
                date=ts.strftime("%Y-%m-%d"),
                time=ts.strftime("%H:%M"),
            ).render()
            url_records.append({"tag": url_job.tag, "prompt": prompt})

        url_table = ibis.memtable(url_records)
        requests = build_batch_requests(_table_to_pylist(url_table), url_model)

        responses = text_batch_client.generate_content(
            requests,
            display_name="Egregora URL Enrichment",
        )

        result_map = map_batch_results(responses)
        for url_job in pending_url_jobs:
            result = result_map.get(url_job.tag)
            if not result or result.error or not result.response:
                logger.warning(
                    "Failed to enrich URL %s: %s",
                    url_job.url,
                    result.error if result else "no result",
                )
                url_job.markdown = f"[Failed to enrich URL: {url_job.url}]"
                continue

            markdown_content = (result.response.text or "").strip()
            if not markdown_content:
                markdown_content = f"[No enrichment generated for URL: {url_job.url}]"

            url_job.markdown = markdown_content
            cache.store(url_job.key, {"markdown": markdown_content, "type": "url"})

    pending_media_jobs = [job for job in media_jobs if job.markdown is None]
    if pending_media_jobs:
        media_records = []
        for media_job in pending_media_jobs:
            uploaded_file = vision_batch_client.upload_file(
                path=str(media_job.file_path),
                display_name=media_job.file_path.name,
            )
            media_job.upload_uri = getattr(uploaded_file, "uri", None)
            media_job.mime_type = getattr(uploaded_file, "mime_type", None)

            ts = _ensure_datetime(media_job.timestamp)
            try:
                media_path = media_job.file_path.relative_to(docs_dir)
            except ValueError:
                media_path = media_job.file_path

            prompt = DetailedMediaEnrichmentPromptTemplate(
                media_type=media_job.media_type or "unknown",
                media_filename=media_job.file_path.name,
                media_path=str(media_path),
                original_message=media_job.original_message,
                sender_uuid=media_job.sender_uuid,
                date=ts.strftime("%Y-%m-%d"),
                time=ts.strftime("%H:%M"),
            ).render()
            media_records.append(
                {
                    "tag": media_job.tag,
                    "prompt": prompt,
                    "file_uri": media_job.upload_uri,
                    "mime_type": media_job.mime_type,
                }
            )

        media_responses: list[BatchPromptResult] = []
        if media_records:
            media_table = ibis.memtable(media_records)
            records = _table_to_pylist(media_table)
            requests = build_batch_requests(records, vision_model, include_file=True)

            if requests:
                media_responses = vision_batch_client.generate_content(
                    requests,
                    display_name="Egregora Media Enrichment",
                )

        result_map = map_batch_results(media_responses)
        for media_job in pending_media_jobs:
            if media_job.markdown is not None:
                continue

            result = result_map.get(media_job.tag)
            if not result or result.error or not result.response:
                logger.warning(
                    "Failed to enrich media %s: %s",
                    media_job.file_path.name,
                    result.error if result else "no result",
                )
                media_job.markdown = f"[Failed to enrich media: {media_job.file_path.name}]"
                continue

            markdown_content = (result.response.text or "").strip()
            if not markdown_content:
                markdown_content = (
                    f"[No enrichment generated for media: {media_job.file_path.name}]"
                )

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
                except Exception as delete_error:
                    logger.error("Failed to delete %s: %s", media_job.file_path, delete_error)

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
                "message": (
                    f"[Media Enrichment] {media_job.file_path.name}\n"
                    f"Enrichment saved: {media_job.path}"
                ),
                "original_line": "",
                "tagged_line": "",
            }
        )

    if pii_media_deleted:

        @ibis.udf.scalar.python
        def replace_media_udf(message: str) -> str:
            return (
                replace_media_mentions(message, media_mapping, docs_dir, posts_dir)
                if message
                else message
            )

        messages_table = messages_table.mutate(message=replace_media_udf(messages_table.message))

    if not new_rows:
        return messages_table

    # TENET-BREAK: Downstream consumers (e.g., writer) expect CONVERSATION_SCHEMA
    # and will fail if extra columns are present.
    # To isolate enrichment from upstream changes, we filter `messages_table`
    # to match the core schema before uniting it with `enrichment_table`.
    # This ensures that `enrich_table` always returns a table with a predictable
    # schema, preventing downstream errors.
    schema = CONVERSATION_SCHEMA
    # Normalize rows to match schema, filling missing columns with None
    normalized_rows = [{column: row.get(column) for column in schema.names} for row in new_rows]
    enrichment_table = ibis.memtable(normalized_rows, schema=schema)

    # Filter messages_table to only include columns from CONVERSATION_SCHEMA
    messages_table_filtered = messages_table.select(*schema.names)

    # Ensure timestamp column is in UTC to match CONVERSATION_SCHEMA
    messages_table_filtered = messages_table_filtered.mutate(
        timestamp=messages_table_filtered.timestamp.cast("timestamp('UTC', 9)")
    )

    combined = messages_table_filtered.union(enrichment_table, distinct=False)
    combined = combined.order_by("timestamp")

    if (duckdb_connection is None) != (target_table is None):
        raise ValueError(
            "duckdb_connection and target_table must be provided together when persisting"
        )

    if duckdb_connection and target_table:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", target_table):
            raise ValueError("target_table must be a valid DuckDB identifier")

        database_schema.create_table_if_not_exists(
            duckdb_connection,
            target_table,
            CONVERSATION_SCHEMA,
        )

        temp_view = f"_egregora_enrichment_{uuid.uuid4().hex}"
        ordered_expr = combined.order_by("timestamp")
        duckdb_connection.create_view(temp_view, ordered_expr, overwrite=True)
        try:
            duckdb_connection.raw_sql(f"DELETE FROM {target_table}")
            duckdb_connection.raw_sql(
                f"INSERT INTO {target_table} SELECT * FROM {temp_view}"
            )
        finally:
            duckdb_connection.drop_view(temp_view, force=True)

    if pii_detected_count > 0:
        logger.info(
            "Privacy summary: %d media file(s) deleted due to PII detection",
            pii_detected_count,
        )

    if persist_connection and persist_table and normalized_rows:
        column_list = ", ".join(schema.names)
        placeholders = ", ".join(["?"] * len(schema.names))
        persist_connection.executemany(
            f"INSERT INTO {persist_table} ({column_list}) VALUES ({placeholders})",
            [tuple(row[column] for column in schema.names) for row in normalized_rows],
        )

    return combined
