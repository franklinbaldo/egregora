"""Simple enrichment: extract media, add LLM-described context as table rows.

Enrichment adds context for URLs and media as new table rows with author 'egregora'.
The LLM sees enrichment context inline with original messages.

Documentation:
- Architecture (Enricher): docs/guides/architecture.md#4-enricher-enricherpy
- Core Concepts: docs/getting-started/concepts.md#4-enrich-optional
"""

import hashlib
import logging
import os
import re
import uuid
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import ibis
from google.genai import types as genai_types
from ibis.expr.types import Table

from ..utils import EnrichmentCache, make_enrichment_cache_key
from ..config import EnrichmentConfig, ModelConfig, MEDIA_DIR_NAME
from ..utils import BatchPromptRequest, BatchPromptResult, GeminiBatchClient, call_with_retries
from ..prompt_templates import (
    render_media_enrichment_detailed_prompt,
    render_url_enrichment_detailed_prompt,
)

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

# WhatsApp attachment markers (special Unicode)
ATTACHMENT_MARKERS = (
    "(arquivo anexado)",
    "(file attached)",
    "(archivo adjunto)",
    "\u200e<attached:",  # Unicode left-to-right mark + <attached:
)

# Media type detection by extension
MEDIA_EXTENSIONS = {
    # Images
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    # Videos
    ".mp4": "video",
    ".mov": "video",
    ".3gp": "video",
    ".avi": "video",
    # Audio
    ".opus": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    # Documents
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
}


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


def _ensure_datetime(value: Any) -> datetime:
    """Convert pandas/ibis timestamp objects to ``datetime``."""
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


def _safe_timestamp_plus_one(timestamp: Any) -> Any:
    """Return timestamp + 1 second, handling pandas/ibis types."""
    dt_value = _ensure_datetime(timestamp)
    return dt_value + timedelta(seconds=1)
def _table_to_pylist(table: Table) -> list[dict[str, Any]]:
    """Convert an Ibis table to a list of dictionaries without heavy dependencies."""

    to_pylist = getattr(table, "to_pylist", None)
    if callable(to_pylist):
        return list(to_pylist())

    records = table.execute().to_dict("records")
    return [dict(record) for record in records]


def build_batch_requests(
    records: list[dict[str, Any]],
    model: str,
    *,
    include_file: bool = False,
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
        }

        if not include_file:
            request_kwargs["config"] = genai_types.GenerateContentConfig(temperature=0.3)

        requests.append(BatchPromptRequest(**request_kwargs))

    return requests


def map_batch_results(
    responses: list[BatchPromptResult],
) -> dict[str | None, BatchPromptResult]:
    """Return a mapping from result tag to the ``BatchPromptResult``."""

    return {result.tag: result for result in responses}


def get_media_subfolder(file_extension: str) -> str:
    """Get subfolder based on media type."""
    ext = file_extension.lower()
    media_type = MEDIA_EXTENSIONS.get(ext, "file")

    if media_type == "image":
        return "images"
    elif media_type == "video":
        return "videos"
    elif media_type == "audio":
        return "audio"
    elif media_type == "document":
        return "documents"
    else:
        return "files"


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text."""
    if not text:
        return []
    return URL_PATTERN.findall(text)


def find_media_references(text: str) -> list[str]:
    """
    Find media filenames in WhatsApp messages.

    WhatsApp marks media with special patterns like:
    - "IMG-20250101-WA0001.jpg (arquivo anexado)"
    - "<attached: IMG-20250101-WA0001.jpg>"
    """
    if not text:
        return []

    media_files = []

    # Pattern 1: filename before attachment marker
    # "IMG-20250101-WA0001.jpg (file attached)"
    for marker in ATTACHMENT_MARKERS:
        pattern = r"([\w\-\.]+\.\w+)\s*" + re.escape(marker)
        matches = re.findall(pattern, text, re.IGNORECASE)
        media_files.extend(matches)

    # Pattern 2: WhatsApp standard filenames (without marker)
    # "IMG-20250101-WA0001.jpg"
    wa_pattern = r"\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b"
    wa_matches = re.findall(wa_pattern, text)
    media_files.extend(wa_matches)

    return list(set(media_files))  # Deduplicate


def extract_media_from_zip(
    zip_path: Path,
    filenames: set[str],
    docs_dir: Path,
    group_slug: str,
) -> dict[str, Path]:
    """
    Extract media files from ZIP and save to output_dir/media/.

    Returns dict mapping original filename to saved path.
    """
    if not filenames:
        return {}

    media_dir = docs_dir / MEDIA_DIR_NAME
    media_dir.mkdir(parents=True, exist_ok=True)

    # Create deterministic namespace for UUID generation
    namespace = uuid.uuid5(uuid.NAMESPACE_DNS, group_slug)

    extracted = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            filename = Path(info.filename).name

            # Check if this file is in our wanted list
            if filename not in filenames:
                continue

            # Read file content
            file_content = zf.read(info)

            # Generate deterministic UUID based on content
            content_hash = hashlib.sha256(file_content).hexdigest()
            file_uuid = uuid.uuid5(namespace, content_hash)

            # Get file extension and subfolder
            file_ext = Path(filename).suffix
            subfolder = get_media_subfolder(file_ext)

            # Create destination path
            subfolder_path = media_dir / subfolder
            subfolder_path.mkdir(parents=True, exist_ok=True)

            new_filename = f"{file_uuid}{file_ext}"
            dest_path = subfolder_path / new_filename

            # Save file if not already exists
            if not dest_path.exists():
                dest_path.write_bytes(file_content)

            extracted[filename] = dest_path.resolve()

    return extracted


def replace_media_mentions(
    text: str,
    media_mapping: dict[str, Path],
    docs_dir: Path,
    posts_dir: Path,
) -> str:
    """
    Replace WhatsApp media filenames with new UUID5 paths.

    "Check this IMG-20250101-WA0001.jpg (file attached)"
    → "Check this ![Image](media/images/abc123def.jpg)"
    """
    if not text or not media_mapping:
        return text

    result = text

    for original_filename, new_path in media_mapping.items():
        # Compute the link target we expect inside posts directory
        try:
            relative_link = Path(os.path.relpath(new_path, posts_dir)).as_posix()
        except ValueError:
            try:
                relative_link = "/" + new_path.relative_to(docs_dir).as_posix()
            except ValueError:
                relative_link = new_path.as_posix()

        # Check if media file still exists (might be deleted due to PII)
        if not new_path.exists():
            replacement = "[Media removed: privacy protection]"

            # Replace all occurrences with privacy notice
            for marker in ATTACHMENT_MARKERS:
                pattern = re.escape(original_filename) + r"\s*" + re.escape(marker)
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

            # Also replace bare filename
            result = re.sub(r"\b" + re.escape(original_filename) + r"\b", replacement, result)

            # Replace any previously generated markdown links that point to the deleted file
            image_pattern = r"!\[[^\]]*\]\(" + re.escape(relative_link) + r"\)"
            result = re.sub(image_pattern, replacement, result)
            link_pattern = r"\[[^\]]*\]\(" + re.escape(relative_link) + r"\)"
            result = re.sub(link_pattern, replacement, result)
            continue

        # Get relative path from output_dir
        # Determine if it's an image for markdown rendering
        ext = new_path.suffix.lower()
        is_image = ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]

        # Create markdown link
        if is_image:
            replacement = f"![Image]({relative_link})"
        else:
            replacement = f"[{new_path.name}]({relative_link})"

        # Replace all occurrences with any attachment marker
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(original_filename) + r"\s*" + re.escape(marker)
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Also replace bare filename (without marker)
        result = re.sub(r"\b" + re.escape(original_filename) + r"\b", replacement, result)

    return result


def extract_and_replace_media(
    messages_table: Table,
    zip_path: Path,
    docs_dir: Path,
    posts_dir: Path,
    group_slug: str = "shared",
) -> tuple[Table, dict[str, Path]]:
    """
    Extract media from ZIP and replace mentions in Table.

    Returns:
        - Updated Table with new media paths
        - Media mapping (original → extracted path)
    """
    # Step 1: Find all media references
    all_media = set()
    for row in messages_table.execute().to_dict("records"):
        message = row.get("message", "")
        media_refs = find_media_references(message)
        all_media.update(media_refs)

    # Step 2: Extract from ZIP
    media_mapping = extract_media_from_zip(zip_path, all_media, docs_dir, group_slug)

    if not media_mapping:
        return messages_table, {}

    # Step 3: Replace mentions in Table
    @ibis.udf.scalar.python
    def replace_in_message(message: str) -> str:
        return (
            replace_media_mentions(message, media_mapping, docs_dir, posts_dir)
            if message
            else message
        )

    updated_table = messages_table.mutate(message=replace_in_message(messages_table.message))

    return updated_table, media_mapping


def detect_media_type(file_path: Path) -> str | None:
    """Detect media type from file extension."""
    ext = file_path.suffix.lower()
    for extension, media_type in MEDIA_EXTENSIONS.items():
        if ext == extension:
            return media_type
    return None




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
            prompt = render_url_enrichment_detailed_prompt(
                url=url_job.url,
                original_message=url_job.original_message,
                sender_uuid=url_job.sender_uuid,
                date=ts.strftime("%Y-%m-%d"),
                time=ts.strftime("%H:%M"),
            )
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
                logger.warning("Failed to enrich URL %s: %s", url_job.url, result.error if result else "no result")
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

            prompt = render_media_enrichment_detailed_prompt(
                media_type=media_job.media_type or "unknown",
                media_filename=media_job.file_path.name,
                media_path=str(media_path),
                original_message=media_job.original_message,
                sender_uuid=media_job.sender_uuid,
                date=ts.strftime("%Y-%m-%d"),
                time=ts.strftime("%H:%M"),
            )
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
    normalized_rows = [{column: row.get(column) for column in schema.names} for row in new_rows]

    enrichment_table = ibis.memtable(normalized_rows, schema=schema)
    combined = messages_table.union(enrichment_table, distinct=False)
    combined = combined.order_by("timestamp")

    if pii_detected_count > 0:
        logger.info(
            "Privacy summary: %d media file(s) deleted due to PII detection",
            pii_detected_count,
        )

    return combined
