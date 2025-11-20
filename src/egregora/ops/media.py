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

import hashlib
import logging
import os
import re
import uuid
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.input_adapters.base import InputAdapter


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


def extract_media_from_zip(
    zip_path: Path,
    filenames: set[str],
    media_dir: Path,
) -> dict[str, Path]:
    """Extract media files from ZIP and save to media_dir/.

    UUID generation is based on content only - enables global deduplication.
    Returns dict mapping original filename to saved path.
    """
    if not filenames:
        return {}

    media_dir.mkdir(parents=True, exist_ok=True)
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    extracted = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            filename = Path(info.filename).name
            if filename not in filenames:
                continue

            file_content = zf.read(info)
            content_hash = hashlib.sha256(file_content).hexdigest()
            file_uuid = uuid.uuid5(namespace, content_hash)
            file_ext = Path(filename).suffix

            subfolder = get_media_subfolder(file_ext)
            subfolder_path = media_dir / subfolder
            subfolder_path.mkdir(parents=True, exist_ok=True)

            new_filename = f"{file_uuid}{file_ext}"
            dest_path = subfolder_path / new_filename

            if not dest_path.exists():
                dest_path.write_bytes(file_content)

            extracted[filename] = dest_path.resolve()

    return extracted


# ----------------------------------------------------------------------------
# Reference Replacement (Transformation Stage)
# ----------------------------------------------------------------------------


def replace_media_mentions(
    text: str,
    media_mapping: dict[str, Path],
    docs_dir: Path,
    posts_dir: Path,
) -> str:
    """Replace raw media filenames with new UUID5 paths in text.

    "Check this IMG-2025.jpg (file attached)"
    → "Check this ![Image](media/images/abc123def.jpg)"
    """
    if not text or not media_mapping:
        return text

    result = text
    for original_filename, new_path in media_mapping.items():
        # Calculate relative path for markdown link
        try:
            relative_link = Path(os.path.relpath(new_path, posts_dir)).as_posix()
        except ValueError:
            try:
                relative_link = "/" + new_path.relative_to(docs_dir).as_posix()
            except ValueError:
                relative_link = new_path.as_posix()

        if not new_path.exists():
            # Handle missing/removed media
            replacement = "[Media removed: privacy protection]"
            for marker in ATTACHMENT_MARKERS:
                pattern = re.escape(original_filename) + r"\s*" + re.escape(marker)
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

            result = re.sub(r"\b" + re.escape(original_filename) + r"\b", replacement, result)

            # Fix markdown links if they exist
            result = result.replace(f"]({relative_link})", f"]({replacement})")
            continue

        # Format replacement based on type
        ext = new_path.suffix.lower()
        is_image = ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        replacement = f"![Image]({relative_link})" if is_image else f"[{new_path.name}]({relative_link})"

        # Replace attachments markers + filename
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(original_filename) + r"\s*" + re.escape(marker)
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Replace bare filename occurrences
        result = re.sub(r"\b" + re.escape(original_filename) + r"\b", replacement, result)

    return result


def replace_markdown_media_refs(
    table: Table, media_mapping: dict[str, Path], docs_dir: Path, posts_dir: Path
) -> Table:
    """Replace markdown media references with standardized paths in Ibis table."""
    if not media_mapping:
        return table

    updated_table = table
    for original_ref, absolute_path in media_mapping.items():
        try:
            relative_link = Path(os.path.relpath(absolute_path, posts_dir)).as_posix()
        except ValueError:
            try:
                relative_link = "/" + absolute_path.relative_to(docs_dir).as_posix()
            except ValueError:
                relative_link = absolute_path.as_posix()

        # Replace in text column
        updated_table = updated_table.mutate(
            text=updated_table.text.replace(f"]({original_ref})", f"]({relative_link})")
        )

    return updated_table


def process_media_for_window(
    window_table: Table,
    adapter: InputAdapter,
    media_dir: Path,
    temp_dir: Path,
    docs_dir: Path,
    posts_dir: Path,
    **adapter_kwargs: object,
) -> tuple[Table, dict[str, Path]]:
    """High-level pipeline to process media for a window."""
    media_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    media_refs = extract_markdown_media_refs(window_table)
    if not media_refs:
        return (window_table, {})

    logger.info("Found %s media references to process", len(media_refs))
    media_mapping: dict[str, Path] = {}

    for media_ref in media_refs:
        try:
            # Adapter delivers a Document containing the media content
            document = adapter.deliver_media(media_reference=media_ref, **adapter_kwargs)
            if not document:
                continue

            # Write to temp file to reuse existing standardization logic
            # (standardize_media_file expects a Path currently)
            # TODO: Refactor standardize_media_file to accept content/bytes directly
            temp_file = temp_dir / media_ref
            if isinstance(document.content, bytes):
                temp_file.write_bytes(document.content)
            else:
                temp_file.write_text(document.content, encoding="utf-8")

            standardized_path = adapter.standardize_media_file(
                source_file=temp_file, media_dir=media_dir, get_subfolder=get_media_subfolder
            )
            media_mapping[media_ref] = standardized_path

        except OSError as e:
            logger.warning("Failed to process media '%s': %s", media_ref, e)
            continue

    if media_mapping:
        updated_table = replace_markdown_media_refs(
            window_table, media_mapping, docs_dir=docs_dir, posts_dir=posts_dir
        )
    else:
        updated_table = window_table

    return (updated_table, media_mapping)
