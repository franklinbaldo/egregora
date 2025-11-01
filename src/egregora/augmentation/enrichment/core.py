"""Simple enrichment: extract media, add LLM-described context as table rows.

Enrichment adds context for URLs and media as new table rows with author 'egregora'.
The LLM sees enrichment context inline with original messages.

Documentation:
- Architecture (Enricher): docs/guides/architecture.md#4-enricher-enricherpy
- Core Concepts: docs/getting-started/concepts.md#4-enrich-optional
"""

import logging
import uuid
from pathlib import Path
from typing import Any

import ibis
from ibis.expr.types import Table

from ...config import ModelConfig
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
    replace_media_mentions,
)

logger = logging.getLogger(__name__)


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

    rows = messages_table.execute().to_dict("records")
    new_rows: list[dict[str, Any]] = []
    enrichment_count = 0
    pii_detected_count = 0
    pii_media_deleted = False
    seen_url_keys: set[str] = set()
    seen_media_keys: set[str] = set()

    url_jobs: list[UrlEnrichmentJob] = []
    media_jobs: list[MediaEnrichmentJob] = []

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

        if enable_media and media_mapping:
            for original_filename, file_path in media_mapping.items():
                if original_filename in message or file_path.name in message:
                    if enrichment_count >= max_enrichments:
                        break
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

        url_job.path.parent.mkdir(parents=True, exist_ok=True)
        url_job.path.write_text(url_job.markdown, encoding="utf-8")

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

        media_job.path.parent.mkdir(parents=True, exist_ok=True)
        media_job.path.write_text(media_job.markdown, encoding="utf-8")

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
            return (
                replace_media_mentions(message, media_mapping, docs_dir, posts_dir)
                if message
                else message
            )

        messages_table = messages_table.mutate(message=replace_media_udf(messages_table.message))

    if not new_rows:
        return messages_table

    schema = messages_table.schema()
    # Normalize rows to match schema, filling missing columns with None
    normalized_rows = [
        {column: row.get(column, None) for column in schema.names} for row in new_rows
    ]

    enrichment_table = ibis.memtable(normalized_rows, schema=schema)
    combined = messages_table.union(enrichment_table, distinct=False)
    combined = combined.order_by("timestamp")

    if pii_detected_count > 0:
        logger.info(
            "Privacy summary: %d media file(s) deleted due to PII detection",
            pii_detected_count,
        )

    return combined
