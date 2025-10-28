"""Simple enrichment: extract media, add LLM-described context as DataFrame rows.

Enrichment adds context for URLs and media as new DataFrame rows with author 'egregora'.
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
from datetime import timedelta
from pathlib import Path

import ibis
from google.genai import types as genai_types
from ibis.expr.types import Table

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .cache import EnrichmentCache, make_enrichment_cache_key
from .config_types import EnrichmentConfig
from .gemini_batch import BatchPromptRequest, GeminiBatchClient
from .genai_utils import call_with_retries
from .model_config import ModelConfig
from .prompt_templates import (
    render_media_enrichment_detailed_prompt,
    render_url_enrichment_detailed_prompt,
)
from .site_config import MEDIA_DIR_NAME

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


async def enrich_media(
    *,
    file_path: Path,
    original_message: str,
    sender_uuid: str,
    timestamp: Any,
    config: EnrichmentConfig,
    media_type: str | None = None,
    upload_fn: Callable[..., Awaitable[Any]] | None = None,
    generate_content_fn: Callable[..., Awaitable[Any]] | None = None,
) -> str | None:
    """Enrich a single media file using the legacy async Gemini interface.

    ``enrich_dataframe`` is the preferred batch API, but we keep this helper so
    alpha users that still import :func:`enrich_media` are not broken while the
    migration completes.  The implementation mirrors the previous behaviour:
    upload the media, request a markdown description, persist it under
    ``media/enrichments`` and delete the original file when the model flags
    potential PII.
    """

    docs_dir = config.output_dir
    docs_dir.mkdir(parents=True, exist_ok=True)

    detected_media_type = media_type or detect_media_type(file_path)
    if not detected_media_type:
        logger.warning("Unsupported media type for enrichment: %s", file_path.name)
        return None

    enrichment_dir = docs_dir / MEDIA_DIR_NAME / "enrichments"
    enrichment_dir.mkdir(parents=True, exist_ok=True)
    enrichment_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(file_path.resolve()))
    enrichment_path = enrichment_dir / f"{enrichment_id}.md"

    ts = _ensure_datetime(timestamp)
    try:
        media_path = str(file_path.relative_to(docs_dir))
    except ValueError:
        subfolder = get_media_subfolder(file_path.suffix)
        media_path = str(Path(MEDIA_DIR_NAME) / subfolder / file_path.name)

    prompt = render_media_enrichment_detailed_prompt(
        media_type=detected_media_type,
        media_filename=file_path.name,
        media_path=media_path,
        original_message=original_message,
        sender_uuid=sender_uuid,
        date=ts.strftime("%Y-%m-%d"),
        time=ts.strftime("%H:%M"),
    )

    if upload_fn is None or generate_content_fn is None:
        client = getattr(config, "client", None)
        aio_client = getattr(client, "aio", None) if client is not None else None
        files_client = getattr(aio_client, "files", None) if aio_client else None
        models_client = getattr(aio_client, "models", None) if aio_client else None

        upload_fn = upload_fn or getattr(files_client, "upload", None)
        generate_content_fn = generate_content_fn or getattr(models_client, "generate_content", None)

    if upload_fn is None or generate_content_fn is None:
        raise RuntimeError(
            "Gemini async client missing: provide EnrichmentConfig.client or override upload_fn/generate_content_fn."
        )

    uploaded_file = await call_with_retries(
        upload_fn,
        path=str(file_path),
        display_name=file_path.name,
    )

    parts = [genai_types.Part(text=prompt)]
    upload_uri = getattr(uploaded_file, "uri", None)
    if upload_uri:
        mime_type = getattr(uploaded_file, "mime_type", "application/octet-stream")
        parts.append(
            genai_types.Part(
                file_data=genai_types.FileData(
                    file_uri=upload_uri,
                    mime_type=mime_type,
                    display_name=file_path.name,
                )
            )
        )

    response = await call_with_retries(
        generate_content_fn,
        contents=[genai_types.Content(role="user", parts=parts)],
        model=config.model,
        config=genai_types.GenerateContentConfig(temperature=0.3),
    )

    markdown_content = (getattr(response, "text", None) or "").strip()
    if not markdown_content:
        logger.warning("No enrichment generated for media: %s", file_path.name)
        return None

    if "PII_DETECTED" in markdown_content:
        logger.warning(
            "PII detected in media: %s. Media will be deleted after redaction.",
            file_path.name,
        )
        markdown_content = markdown_content.replace("PII_DETECTED", "").strip()
        try:
            file_path.unlink(missing_ok=True)
            logger.info("Deleted media file containing PII: %s", file_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to delete %s: %s", file_path, exc)

    enrichment_path.write_text(markdown_content, encoding="utf-8")
    logger.info("Saved media enrichment for %s at %s", file_path.name, enrichment_path)
    return str(enrichment_path)


def _ensure_datetime(value):
    """Convert pandas/ibis timestamp objects to ``datetime``."""
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


def _safe_timestamp_plus_one(timestamp) -> Any:
    """Return timestamp + 1 second, handling pandas/ibis types."""
    dt_value = _ensure_datetime(timestamp)
    return dt_value + timedelta(seconds=1)


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
    df: Table,
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
    for row in df.execute().to_dict("records"):
        message = row.get("message", "")
        media_refs = find_media_references(message)
        all_media.update(media_refs)

    # Step 2: Extract from ZIP
    media_mapping = extract_media_from_zip(zip_path, all_media, docs_dir, group_slug)

    if not media_mapping:
        return df, {}

    # Step 3: Replace mentions in Table
    @ibis.udf.scalar.python
    def replace_in_message(message: str) -> str:
        return (
            replace_media_mentions(message, media_mapping, docs_dir, posts_dir)
            if message
            else message
        )

    updated_df = df.mutate(message=replace_in_message(df.message))

    return updated_df, media_mapping


def detect_media_type(file_path: Path) -> str | None:
    """Detect media type from file extension."""
    ext = file_path.suffix.lower()
    for extension, media_type in MEDIA_EXTENSIONS.items():
        if ext == extension:
            return media_type
    return None




def enrich_dataframe(
    df: Table,
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

    if df.count().execute() == 0:
        return df

    rows = df.execute().to_dict("records")
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
                job = UrlEnrichmentJob(
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
                    job.markdown = cache_entry.get("markdown")
                    job.cached = True

                url_jobs.append(job)
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
                    job = MediaEnrichmentJob(
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
                        job.markdown = cache_entry.get("markdown")
                        job.cached = True

                    media_jobs.append(job)
                    seen_media_keys.add(cache_key)
                    enrichment_count += 1

    pending_url_jobs = [job for job in url_jobs if job.markdown is None]
    if pending_url_jobs:
        requests: list[BatchPromptRequest] = []
        for job in pending_url_jobs:
            ts = _ensure_datetime(job.timestamp)
            prompt = render_url_enrichment_detailed_prompt(
                url=job.url,
                original_message=job.original_message,
                sender_uuid=job.sender_uuid,
                date=ts.strftime("%Y-%m-%d"),
                time=ts.strftime("%H:%M"),
            )
            requests.append(
                BatchPromptRequest(
                    contents=[
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part(text=prompt)],
                        )
                    ],
                    config=genai_types.GenerateContentConfig(temperature=0.3),
                    model=url_model,
                    tag=job.tag,
                )
            )

        try:
            responses = text_batch_client.generate_content(
                requests,
                display_name="Egregora URL Enrichment",
            )
        except Exception as exc:
            logger.error("URL enrichment batch failed: %s", exc)
            responses = []

        result_map = {result.tag: result for result in responses}
        for job in pending_url_jobs:
            result = result_map.get(job.tag)
            if not result or result.error or not result.response:
                logger.warning("Failed to enrich URL %s: %s", job.url, result.error if result else "no result")
                job.markdown = f"[Failed to enrich URL: {job.url}]"
                continue

            markdown_content = (result.response.text or "").strip()
            if not markdown_content:
                markdown_content = f"[No enrichment generated for URL: {job.url}]"

            job.markdown = markdown_content
            cache.store(job.key, {"markdown": markdown_content, "type": "url"})

    pending_media_jobs = [job for job in media_jobs if job.markdown is None]
    if pending_media_jobs:
        requests: list[BatchPromptRequest] = []
        for job in pending_media_jobs:
            try:
                uploaded_file = vision_batch_client.upload_file(
                    path=str(job.file_path),
                    display_name=job.file_path.name,
                )
                job.upload_uri = getattr(uploaded_file, "uri", None)
                job.mime_type = getattr(uploaded_file, "mime_type", None)
            except Exception as exc:
                logger.error("Failed to upload media %s: %s", job.file_path.name, exc)
                job.markdown = f"[Failed to upload media for enrichment: {job.file_path.name}]"
                continue

            ts = _ensure_datetime(job.timestamp)
            try:
                media_path = job.file_path.relative_to(docs_dir)
            except ValueError:
                media_path = job.file_path

            prompt = render_media_enrichment_detailed_prompt(
                media_type=job.media_type,
                media_filename=job.file_path.name,
                media_path=str(media_path),
                original_message=job.original_message,
                sender_uuid=job.sender_uuid,
                date=ts.strftime("%Y-%m-%d"),
                time=ts.strftime("%H:%M"),
            )

            parts = [genai_types.Part(text=prompt)]
            if job.upload_uri:
                parts.append(
                    genai_types.Part(
                        file_data=genai_types.FileData(
                            file_uri=job.upload_uri,
                            mime_type=job.mime_type,
                            display_name=job.file_path.name,
                        )
                    )
                )

            requests.append(
                BatchPromptRequest(
                    contents=[
                        genai_types.Content(
                            role="user",
                            parts=parts,
                        )
                    ],
                    model=vision_model,
                    tag=job.tag,
                )
            )

        if requests:
            try:
                responses = vision_batch_client.generate_content(
                    requests,
                    display_name="Egregora Media Enrichment",
                )
            except Exception as exc:
                logger.error("Media enrichment batch failed: %s", exc)
                responses = []
        else:
            responses = []

        result_map = {result.tag: result for result in responses}
        for job in pending_media_jobs:
            if job.markdown is not None:
                continue

            result = result_map.get(job.tag)
            if not result or result.error or not result.response:
                logger.warning(
                    "Failed to enrich media %s: %s",
                    job.file_path.name,
                    result.error if result else "no result",
                )
                job.markdown = f"[Failed to enrich media: {job.file_path.name}]"
                continue

            markdown_content = (result.response.text or "").strip()
            if not markdown_content:
                markdown_content = f"[No enrichment generated for media: {job.file_path.name}]"

            if "PII_DETECTED" in markdown_content:
                logger.warning(
                    "PII detected in media: %s. Media will be deleted after redaction.",
                    job.file_path.name,
                )
                markdown_content = markdown_content.replace("PII_DETECTED", "").strip()
                try:
                    job.file_path.unlink()
                    logger.info("Deleted media file containing PII: %s", job.file_path)
                    pii_media_deleted = True
                    pii_detected_count += 1
                except Exception as delete_error:
                    logger.error("Failed to delete %s: %s", job.file_path, delete_error)

            job.markdown = markdown_content
            cache.store(job.key, {"markdown": markdown_content, "type": "media"})

    for job in url_jobs:
        if not job.markdown:
            continue

        job.path.parent.mkdir(parents=True, exist_ok=True)
        job.path.write_text(job.markdown, encoding="utf-8")

        enrichment_timestamp = _safe_timestamp_plus_one(job.timestamp)
        new_rows.append(
            {
                "timestamp": enrichment_timestamp,
                "date": enrichment_timestamp.date(),
                "author": "egregora",
                "message": f"[URL Enrichment] {job.url}\\nEnrichment saved: {job.path}",
                "original_line": "",
                "tagged_line": "",
            }
        )

    for job in media_jobs:
        if not job.markdown:
            continue

        job.path.parent.mkdir(parents=True, exist_ok=True)
        job.path.write_text(job.markdown, encoding="utf-8")

        enrichment_timestamp = _safe_timestamp_plus_one(job.timestamp)
        new_rows.append(
            {
                "timestamp": enrichment_timestamp,
                "date": enrichment_timestamp.date(),
                "author": "egregora",
                "message": f"[Media Enrichment] {job.file_path.name}\\nEnrichment saved: {job.path}",
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

        df = df.mutate(message=replace_media_udf(df.message))

    if not new_rows:
        return df

    schema = df.schema()
    normalized_rows = [{column: row.get(column) for column in schema.names} for row in new_rows]

    enrichment_df = ibis.memtable(normalized_rows, schema=schema)
    combined = df.union(enrichment_df, distinct=False)
    combined = combined.order_by("timestamp")

    if pii_detected_count > 0:
        logger.info(
            "Privacy summary: %d media file(s) deleted due to PII detection",
            pii_detected_count,
        )

    return combined
