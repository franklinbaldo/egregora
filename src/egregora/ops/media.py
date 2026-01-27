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
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from ibis import udf

from egregora.data_primitives.document import Document, DocumentType, MediaAsset
from egregora.data_primitives.text import slugify

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.data_primitives.document import UrlContext, UrlConvention
    from egregora.input_adapters.base import InputAdapter, MediaMapping


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

# Optimized Patterns for find_media_references
_MARKERS_REGEX = "|".join(re.escape(m) for m in ATTACHMENT_MARKERS)
ATTACHMENT_MARKERS_PATTERN = re.compile(rf"([\w\-\.]+\.\w+)\s*(?:{_MARKERS_REGEX})", re.IGNORECASE)
UNICODE_MEDIA_PATTERN = re.compile(r"\u200e((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)", re.IGNORECASE)

# Split Patterns for optimized extraction
FAST_MEDIA_PATTERN = re.compile(
    r"""
    !\[(?P<img_alt>[^\]]*)\]\((?P<img_url>[^)]+)\) |              # Markdown Image
    (?<!!)\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)]+)\) |      # Markdown Link
    \b(?P<wa_file>(?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b |     # WhatsApp
    (?i:\u200e(?P<uni_file>(?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)) # Unicode
    """,
    re.VERBOSE,
)

MARKER_PATTERN = re.compile(rf"(?:{_MARKERS_REGEX})", re.IGNORECASE)
FILENAME_LOOKBEHIND_PATTERN = re.compile(r"([\w\-\.]+\.\w+)\s*$", re.IGNORECASE)


# ----------------------------------------------------------------------------
# Detection & Classification
# ----------------------------------------------------------------------------


def detect_media_type(
    file_path: Annotated[str | Path, "The path or filename of the media file"],
) -> Annotated[str | None, "The detected media type, or None if unknown"]:
    """Detect media type from file extension."""
    # Optimization: os.path.splitext is significantly faster than Path.suffix for strings
    if isinstance(file_path, str):
        _, ext = os.path.splitext(file_path)
    else:
        ext = file_path.suffix
    return MEDIA_EXTENSIONS.get(ext.lower())


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
    - "‎IMG-20250101-WA0001.jpg" (with U+200E LEFT-TO-RIGHT MARK)
    """
    if not text:
        return []
    media_files = []

    # Pattern 1: Attachment markers (localized strings) - O(1) regex pass instead of O(N) loop
    media_files.extend(ATTACHMENT_MARKERS_PATTERN.findall(text))

    # Pattern 2: WhatsApp filename pattern (IMG-/VID-/AUD-/etc.)
    media_files.extend(WA_MEDIA_PATTERN.findall(text))

    # Pattern 3: Unicode marker (U+200E LEFT-TO-RIGHT MARK) followed by media filename
    media_files.extend(UNICODE_MEDIA_PATTERN.findall(text))

    return list(set(media_files))


def find_all_media_references(text: str, include_uuids: bool = False) -> list[str]:
    """Find all media filenames and references in text.

    This is an extended version of find_media_references that also detects:
    - UUID-based filenames (e.g., 12345678-1234-1234-1234-1234567890ab.png)

    Args:
        text: The text to search for media references
        include_uuids: If True, include UUIDs with any extension.
                      If False, only include UUIDs with known extensions.

    Returns:
        List of unique media filenames found in the text

    """
    if not text:
        return []

    media_files: set[str] = set()

    # Pre-extract UUIDs first to avoid duplicates with plain file pattern
    uuid_filenames: set[str] = set()
    if include_uuids:
        # UUID pattern: 8-4-4-4-12 hex digits with optional extension
        uuid_pattern = re.compile(
            r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})(?:\.(\w+))?\b",
            re.IGNORECASE,
        )
        for match in uuid_pattern.finditer(text):
            uuid_part = match.group(1)
            ext_part = match.group(2)
            if ext_part:
                filename = f"{uuid_part}.{ext_part}"
            else:
                filename = uuid_part
            uuid_filenames.add(filename)
    else:
        # Only include UUIDs with known extensions
        uuid_pattern = re.compile(
            r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\.(\w+)\b",
            re.IGNORECASE,
        )
        for match in uuid_pattern.finditer(text):
            uuid_part = match.group(1)
            ext_part = match.group(2)
            # Only include if extension is in known media extensions
            if f".{ext_part.lower()}" in MEDIA_EXTENSIONS:
                filename = f"{uuid_part}.{ext_part}"
                uuid_filenames.add(filename)

    media_files.update(uuid_filenames)

    # Extract all basic media references (WhatsApp, markdown, attachments, etc.)
    # Pass 1: Markdown images ![alt](url)
    markdown_img_pattern = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
    for match in markdown_img_pattern.finditer(text):
        url = match.group(1)
        # Extract just the filename from URLs
        if "/" in url:
            filename = url.split("/")[-1]
        else:
            filename = url
        if filename:
            media_files.add(filename)

    # Pass 2: Markdown links [text](url)
    markdown_link_pattern = re.compile(r"(?<!!)\[(?:[^\]]+)\]\(([^)]+)\)")
    for match in markdown_link_pattern.finditer(text):
        url = match.group(1)
        # Extract just the filename from URLs
        if "/" in url:
            filename = url.split("/")[-1]
        else:
            filename = url
        # Only add non-URL links (local references)
        if filename and not filename.startswith(("http://", "https://")):
            media_files.add(filename)

    # Pass 3: Plain text filenames (pattern: word characters, dots, hyphens with extension)
    # Exclude UUID patterns to avoid double-processing
    plain_file_pattern = re.compile(r"\b([\w\-\.]+\.\w{2,})\b")
    for match in plain_file_pattern.finditer(text):
        filename = match.group(1)
        # Skip if this is a UUID we've already processed
        if filename in uuid_filenames:
            continue
        # Filter out common non-media extensions and very short extensions
        ext = filename.split(".")[-1].lower()
        if ext not in ("com", "org", "net", "io", "co", "de", "fr", "uk"):
            # Also skip files that look like UUIDs
            if not re.match(
                r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.", filename, re.IGNORECASE
            ):
                media_files.add(filename)

    # Pass 4: Attachment markers pattern
    media_files.update(ATTACHMENT_MARKERS_PATTERN.findall(text))

    # Pass 5: WhatsApp file pattern
    media_files.update(WA_MEDIA_PATTERN.findall(text))

    # Pass 6: Unicode WhatsApp pattern
    media_files.update(UNICODE_MEDIA_PATTERN.findall(text))

    return sorted(media_files)


def extract_media_references(table: Table) -> set[str]:
    """Extract all media references (markdown and raw) from message column."""
    references: set[str] = set()
    # IR v1: use "text" column
    try:
        df = table.select("text").execute()
    except (AttributeError, Exception):
        # Fallback if backend interaction fails
        return references

    if hasattr(df, "text"):
        # pandas DataFrame
        # Optimization: distinct messages to avoid redundant regex processing
        messages = df["text"].dropna().unique().tolist()
    elif hasattr(df, "to_pylist"):
        # pyarrow Table
        # Optimization: distinct messages to avoid redundant regex processing
        # Use column iterator to avoid full table conversion
        messages = list({x for x in df["text"].to_pylist() if x})
    else:
        # Fallback for unexpected type
        return references

    # Pre-bind regex methods for optimization
    fast_find = FAST_MEDIA_PATTERN.finditer
    marker_find = MARKER_PATTERN.finditer
    filename_search = FILENAME_LOOKBEHIND_PATTERN.search

    for message in messages:
        if not message or not isinstance(message, str):
            continue

        # Pass 1: Fast patterns (Images, Links, WhatsApp, Unicode)
        for match in fast_find(message):
            # Optimization: Use lastgroup to avoid checking all groups
            group_name = match.lastgroup
            val = match.group(group_name)

            if group_name == "img_url":
                references.add(val)
            elif group_name == "link_url":
                if not val.startswith(("http://", "https://")):
                    references.add(val)
            elif group_name == "wa_file":
                references.add(val)
            elif group_name == "uni_file":
                references.add(val)

        # Pass 2: Attachments via markers (optimized to avoid greedy filename scanning)
        for match in marker_find(message):
            start_pos = match.start()
            lookback_slice = message[:start_pos]
            if not lookback_slice:
                continue

            # Look for filename at the end of the preceding text
            if fm := filename_search(lookback_slice):
                references.add(fm.group(1))

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


class MediaReplacer:
    """Optimized replacement for media mentions using a single regex pass.

    This replaces the O(N * M) logic of iterating through all mapped files for every
    text segment with an O(M + T) approach (compiled regex + single scan).
    """

    def __init__(self, media_mapping: MediaMapping) -> None:
        """Initialize the replacer with a mapping of filenames to media documents."""
        self.media_mapping = media_mapping
        # Map lowercase to original key for case-insensitive lookup
        self.lookup = {k.lower(): k for k in media_mapping}

        # Sort by length descending to ensure longest match priority
        # e.g., match "image-123.jpg" before "image-1.jpg" if overlapping (rare with \b but safer)
        sorted_filenames = sorted(media_mapping.keys(), key=len, reverse=True)

        if not sorted_filenames:
            self.pattern = None
            return

        # Pattern parts
        files_pattern = "|".join(re.escape(f) for f in sorted_filenames)
        markers_pattern = "|".join(re.escape(m) for m in ATTACHMENT_MARKERS)

        # Combined Pattern: \b(filename)\b(?:\s*(marker))?
        # Matches the filename at a word boundary, optionally followed by an attachment marker.
        # This covers both cases: "file.jpg (attached)" and "file.jpg" (bare).
        self.pattern = re.compile(
            rf"\b({files_pattern})\b(?:\s*(?:{markers_pattern}))?",
            re.IGNORECASE,
        )

    def replace(self, text: str) -> str:
        """Replace media mentions in text with their markdown equivalents."""
        if not text or not self.pattern:
            return text

        def replacer_func(match: re.Match) -> str:
            full_match = match.group(0)
            filename_part = match.group(1)

            original_filename = self.lookup.get(filename_part.lower())
            if not original_filename:
                # Should not be reachable if regex is correct
                return full_match

            media_doc = self.media_mapping[original_filename]

            # Check for PII deletion
            if media_doc.metadata.get("pii_deleted"):
                return f"[Media Redacted: {original_filename} contains PII]"

            public_url = media_doc.metadata.get("public_url")
            if not public_url:
                # If we don't have a URL, skip replacement (return original text)
                return full_match

            media_type = media_doc.metadata.get("media_type")
            display_name = media_doc.metadata.get("filename") or original_filename

            if media_type == "image":
                return f"![Image]({public_url})"
            return f"[{display_name}]({public_url})"

        return self.pattern.sub(replacer_func, text)


def replace_media_mentions(
    text: str,
    media_mapping: MediaMapping,
) -> str:
    """Replace raw media filenames with canonical URLs in plain text."""
    if not text or not media_mapping:
        return text
    return MediaReplacer(media_mapping).replace(text)


def replace_media_references(table: Table, media_mapping: MediaMapping) -> Table:
    """Replace media references (markdown and raw) with canonical URLs in Ibis table.

    This function uses an Ibis User-Defined Function (UDF) to avoid deep recursion
    in the expression tree, which can cause a RecursionError in sqlglot.
    The UDF applies all replacements in a single pass within the backend.
    """
    if not media_mapping:
        return table

    # Pre-compile the replacer logic once for the entire table operation
    replacer = MediaReplacer(media_mapping)

    # The UDF is defined as a closure to capture the `replacer` instance.
    @udf.scalar.python
    def _replace_all_media(text: str | None) -> str | None:
        """Performs all media replacements for a single text value."""
        if not text or not isinstance(text, str):
            return text
        return replacer.replace(text)

    # Apply the UDF to the 'text' column.
    return table.mutate(text=_replace_all_media(table.text))


def process_media_for_window(
    window_table: Table,
    adapter: InputAdapter,
    url_convention: UrlConvention,
    url_context: UrlContext,
    **_adapter_kwargs: object,
) -> tuple[Table, MediaMapping]:
    """High-level pipeline to process media for a window."""
    media_refs = extract_media_references(window_table)
    if not media_refs:
        return (window_table, {})

    logger.info("Found %s media references to process", len(media_refs))
    media_mapping: MediaMapping = {}

    for media_ref in media_refs:
        # Optimization: Don't extract media content here.
        # We create a lightweight placeholder document.
        # The actual content processing happens during enrichment.

        # Infer basic metadata from filename
        # Optimization: Avoid Path instantiation for simple extension check
        media_type = detect_media_type(media_ref) or "file"

        # Create placeholder document
        # We use a deterministic ID based on the reference
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, media_ref))

        document = Document(
            content=b"",  # Empty content
            type=DocumentType.MEDIA,
            id=doc_id,
            metadata={
                "original_filename": media_ref,
                "media_type": media_type,
                "nav_exclude": True,
                "hide": ["navigation"],
            },
        )

        try:
            media_doc: Document = _prepare_media_document(document, media_ref)
        except (ValueError, TypeError) as exc:
            logger.warning("Invalid document structure for '%s': %s", media_ref, exc)
            continue
        except AttributeError as exc:
            logger.warning("Missing required attributes for media '%s': %s", media_ref, exc)
            continue

        public_url = url_convention.canonical_url(media_doc, url_context)
        media_doc = media_doc.with_metadata(public_url=_normalize_public_url(public_url))
        media_mapping[media_ref] = media_doc

    updated_table = replace_media_references(window_table, media_mapping) if media_mapping else window_table

    return (updated_table, media_mapping)


def _prepare_media_document(document: Document, media_ref: str) -> MediaAsset:
    """Return a MediaAsset with deterministic naming and metadata."""
    raw_content = document.content
    payload = raw_content if isinstance(raw_content, bytes) else str(raw_content).encode("utf-8")

    metadata = document.metadata.copy()
    original_filename = metadata.get("original_filename") or media_ref
    extension_source = metadata.get("filename") or media_ref

    # Optimization: os.path.splitext is ~5x faster than Path.suffix
    _, extension = os.path.splitext(extension_source)

    media_type = metadata.get("media_type") or detect_media_type(extension_source)

    # media_ref is guaranteed to be a string here
    _, ref_suffix = os.path.splitext(media_ref)
    media_subdir = get_media_subfolder(extension or ref_suffix)

    filename = metadata.get("filename")
    slug_hint = metadata.get("slug")
    if not slug_hint and original_filename:
        slug_hint = slugify(Path(original_filename).stem, lowercase=False)
    if not filename:
        safe_slug = slugify(slug_hint, lowercase=False) if slug_hint else metadata.get("filename", "")
        slug_base = safe_slug or Path(extension_source or "").stem or document.document_id[:8]
        # Hash suffix removed per user request to simplify filename matching
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
        stem = Path(original_filename).stem
        metadata["slug"] = slugify(stem, lowercase=False)
    metadata.setdefault("nav_exclude", True)
    metadata["media_subdir"] = media_subdir
    hide_flags = metadata.get("hide", [])
    if isinstance(hide_flags, str):
        hide_flags = [hide_flags]
    if "navigation" not in hide_flags:
        hide_flags.append("navigation")
    metadata["hide"] = hide_flags

    # Explicitly cast Document to MediaAsset since they share structure but types might differ
    # MediaAsset expects 'bytes' content, while Document can be 'str | bytes'
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
    content = document.content
    if not isinstance(content, bytes):
        if isinstance(content, str):
            content = content.encode("utf-8")
        else:
            msg = f"Media content must be bytes, got {type(content)}"
            raise TypeError(msg)

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
