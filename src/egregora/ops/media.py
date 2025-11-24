"""Unified media operations for handling attachments and references.

This module consolidates media handling logic previously split between:
- `enrichment/media.py` (Extraction from raw sources)
- `transformations/media.py` (Processing markdown references)

It provides a single place for:
- Regex patterns for media detection
- Media extraction and deduplication
- Markdown reference replacement
- Media type detection
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from egregora.data_primitives.document import Document, DocumentType, MediaAsset
from egregora.data_primitives.protocols import UrlContext, UrlConvention
from egregora.input_adapters.base import InputAdapter, MediaMapping
from egregora.utils.paths import slugify

if TYPE_CHECKING:
    from ibis.expr.types import Table


logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Constants & Patterns
# ----------------------------------------------------------------------------

ATTACHMENT_MARKERS = (
    "(arquivo anexado)",
    "(file attached)",
    "(archivo adjunto)",
    "\u200e<attached:",
)

MEDIA_EXTENSIONS = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    ".mp4": "video",
    ".mov": "video",
    ".3gp": "video",
    ".avi": "video",
    ".opus": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
}

# Patterns for raw source extraction (e.g. WhatsApp)
WA_MEDIA_PATTERN = re.compile(r"\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b")
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

# Patterns for Markdown processing
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")


# ----------------------------------------------------------------------------
# Detection & Classification
# ----------------------------------------------------------------------------


def detect_media_type(
    file_path: Annotated[Path, "The path to the media file"],
) -> Annotated[str | None, "The detected media type, or None if unknown"]:
    """Detect media type from file extension."""
    ext = file_path.suffix.lower()
    return MEDIA_EXTENSIONS.get(ext)


def get_media_subfolder(
    file_extension: Annotated[str, "The file extension, e.g., '.jpg'"],
) -> Annotated[str, "The name of the subfolder for this media type"]:
    """Get subfolder based on media type."""
    ext = file_extension.lower()
    media_type = MEDIA_EXTENSIONS.get(ext, "file")
    if media_type == "image":
        return "images"
    if media_type == "video":
        return "videos"
    if media_type == "audio":
        return "audio"
    if media_type == "document":
        return "documents"
    return "files"


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text."""
    if not text:
        return []
    return URL_PATTERN.findall(text)


def find_media_references(text: str) -> list[str]:
    """Find media filenames in text (raw source format).

    Detects patterns like:
    - "IMG-20250101-WA0001.jpg (file attached)"
    - "<attached: IMG-20250101-WA0001.jpg>"
    """
    if not text:
        return []
    media_files = []
    for marker in ATTACHMENT_MARKERS:
        pattern = r"([\w\-\.]+\.\w+)\s*" + re.escape(marker)
        matches = re.findall(pattern, text, re.IGNORECASE)
        media_files.extend(matches)

    wa_matches = WA_MEDIA_PATTERN.findall(text)
    media_files.extend(wa_matches)
    return list(set(media_files))


def extract_markdown_media_refs(table: Table) -> set[str]:
    """Extract all markdown media references from message column."""
    references = set()
    # IR v1: use "text" column
    messages = table.select("text").execute()
    for row in messages.itertuples(index=False):
        message = row.text
        if not message:
            continue
        for match in MARKDOWN_IMAGE_PATTERN.finditer(message):
            references.add(match.group(2))
        for match in MARKDOWN_LINK_PATTERN.finditer(message):
            ref = match.group(2)
            if not ref.startswith(("http://", "https://")):
                references.add(ref)
    return references


# ----------------------------------------------------------------------------
# Extraction & Deduplication (Enrichment Stage)
# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
# Reference Replacement (Transformation Stage)
# ----------------------------------------------------------------------------


def _normalize_public_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith(("http://", "https://", "/")):
        return value
    return "/" + value.lstrip("/")


def _media_public_url(media_doc: Document) -> str | None:
    url = media_doc.metadata.get("public_url")
    if url:
        return _normalize_public_url(url)
    if media_doc.suggested_path:
        return _normalize_public_url(media_doc.suggested_path.strip("/"))
    return None


def replace_media_mentions(
    text: str,
    media_mapping: MediaMapping,
) -> str:
    """Replace raw media filenames with canonical URLs in plain text."""
    if not text or not media_mapping:
        return text

    result = text
    for original_filename, media_doc in media_mapping.items():
        public_url = _media_public_url(media_doc)
        if not public_url:
            continue

        media_type = media_doc.metadata.get("media_type")
        display_name = media_doc.metadata.get("filename") or original_filename
        replacement = (
            f"![Image]({public_url})" if media_type == "image" else f"[{display_name}]({public_url})"
        )

        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(original_filename) + r"\s*" + re.escape(marker)
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        result = re.sub(r"\b" + re.escape(original_filename) + r"\b", replacement, result)

    return result


def replace_markdown_media_refs(table: Table, media_mapping: MediaMapping) -> Table:
    """Replace markdown media references with canonical URLs in Ibis table."""
    if not media_mapping:
        return table

    updated_table = table
    for original_ref, media_doc in media_mapping.items():
        public_url = _media_public_url(media_doc)
        if not public_url:
            continue
        updated_table = updated_table.mutate(
            text=updated_table.text.replace(f"]({original_ref})", f"]({public_url})")
        )

    return updated_table


def process_media_for_window(
    window_table: Table,
    adapter: InputAdapter,
    url_convention: UrlConvention,
    url_context: UrlContext,
    **adapter_kwargs: object,
) -> tuple[Table, MediaMapping]:
    """High-level pipeline to process media for a window."""
    media_refs = extract_markdown_media_refs(window_table)
    if not media_refs:
        return (window_table, {})

    logger.info("Found %s media references to process", len(media_refs))
    media_mapping: MediaMapping = {}

    for media_ref in media_refs:
        try:
            document = adapter.deliver_media(media_reference=media_ref, **adapter_kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to deliver media '%s': %s", media_ref, exc)
            continue

        if not document:
            continue

        try:
            media_doc = _prepare_media_document(document, media_ref)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to normalize media '%s': %s", media_ref, exc)
            continue

        public_url = url_convention.canonical_url(media_doc, url_context)
        media_doc = media_doc.with_metadata(public_url=_normalize_public_url(public_url))
        media_mapping[media_ref] = media_doc

    updated_table = (
        replace_markdown_media_refs(window_table, media_mapping) if media_mapping else window_table
    )

    return (updated_table, media_mapping)


def _prepare_media_document(document: Document, media_ref: str) -> MediaAsset:
    """Return a MediaAsset with deterministic naming and metadata."""
    raw_content = document.content
    if isinstance(raw_content, bytes):
        payload = raw_content
    else:
        payload = str(raw_content).encode("utf-8")

    metadata = document.metadata.copy()
    original_filename = metadata.get("original_filename") or media_ref
    extension_source = metadata.get("filename") or media_ref
    extension = Path(extension_source).suffix
    media_type = metadata.get("media_type") or detect_media_type(Path(extension_source))
    media_subdir = get_media_subfolder(extension or Path(media_ref).suffix)

    filename = metadata.get("filename")
    slug_hint = metadata.get("slug")
    if not slug_hint and original_filename:
        slug_hint = slugify(Path(original_filename).stem)
    if not filename:
        safe_slug = slugify(slug_hint) if slug_hint else metadata.get("filename", "")
        slug_base = safe_slug or Path(extension_source or "").stem or document.document_id[:8]
        unique_suffix = document.document_id[:8]
        if unique_suffix not in slug_base:
            slug_base = f"{slug_base}-{unique_suffix}"
        filename = f"{slug_base}{extension}"

    suggested_path = metadata.get("suggested_path") or f"media/{media_subdir}/{filename}"

    metadata.update(
        {
            "original_filename": original_filename,
            "media_type": media_type,
            "filename": filename,
        }
    )
    if "slug" not in metadata and original_filename:
        metadata["slug"] = slugify(Path(original_filename).stem)
    metadata.setdefault("nav_exclude", True)
    metadata["media_subdir"] = media_subdir
    hide_flags = metadata.get("hide", [])
    if isinstance(hide_flags, str):
        hide_flags = [hide_flags]
    if "navigation" not in hide_flags:
        hide_flags.append("navigation")
    metadata["hide"] = hide_flags

    return MediaAsset(
        content=payload,
        type=DocumentType.MEDIA,
        metadata=metadata,
        parent_id=document.parent_id,
        parent=document.parent,
        created_at=document.created_at,
        source_window=document.source_window,
        suggested_path=suggested_path,
    )


def save_media_asset(document: Document, output_dir: Path) -> Path:
    """Save media document to disk with content-based deterministic naming.

    Args:
        document: The document containing media content (Document or MediaAsset)
        output_dir: Base directory to save the media (files will be saved directly here)

    Returns:
        Path to the saved file

    """
    import hashlib
    import mimetypes

    content = document.content
    if not isinstance(content, bytes):
        if isinstance(content, str):
            content = content.encode("utf-8")
        else:
            raise TypeError(f"Media content must be bytes, got {type(content)}")

    mime_type = document.metadata.get("mime_type", "application/octet-stream")
    file_extension = mimetypes.guess_extension(mime_type) or ".bin"
    # Use content hash for deterministic, collision-resistant naming
    content_hash = hashlib.sha256(content).hexdigest()
    filename = f"media-{content_hash[:32]}{file_extension}"
    file_path = output_dir / filename

    output_dir.mkdir(parents=True, exist_ok=True)
    with file_path.open("wb") as f:
        f.write(content)
    logger.info("Media saved: %s (%d bytes)", file_path.name, len(content))
    return file_path
