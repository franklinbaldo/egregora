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

<<<<<<< HEAD
<<<<<<< HEAD
# Combined pattern for efficient single-pass extraction (replaces multiple regex passes)
COMBINED_ENRICHMENT_PATTERN = re.compile(
    r"""
    # 1. Markdown Link (extract filename)
    (?:(?:!\[|\[)[^\]]*\]\([^)]*?(?P<md_file>[^/)]+\.\w+)\)) |

    # 2. WhatsApp Patterns
    (?P<wa_file>\b(?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+\b) |
    (?:\u200e(?P<uni_file>(?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)) |

    # 3. Generic Filename (matches any filename, optionally with marker)
    # This covers Attachment Markers, Simple Media, and UUIDs in one pass.
    # We use a broad pattern and filter in Python to avoid backtracking overhead.
    \b(?P<gen_file>[\w\-\.]+\.\w+)\b(?P<gen_marker>\s*(?:"""
    + _MARKERS_REGEX
    + r"""))?
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Regex for validating UUIDs (extracted from generic match)
UUID_VALIDATION_PATTERN = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.\w+$", re.IGNORECASE
)

=======
>>>>>>> origin/pr/2707
# Split Patterns for optimized extraction
FAST_MEDIA_PATTERN = re.compile(
    r"""
    !\[(?P<img_alt>[^\]]*)\]\((?P<img_url>[^)]+)\) |              # Markdown Image
<<<<<<< HEAD
    \[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)]+)\) |            # Markdown Link
=======
    (?<!!)\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^)]+)\) |      # Markdown Link
>>>>>>> origin/pr/2707
    \b(?P<wa_file>(?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b |     # WhatsApp
    (?i:\u200e(?P<uni_file>(?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)) # Unicode
    """,
    re.VERBOSE,
)

MARKER_PATTERN = re.compile(rf"(?:{_MARKERS_REGEX})", re.IGNORECASE)
<<<<<<< HEAD
# Anchored validation pattern for manual extraction
# Matches [\w\-\.]+\.\w+ exactly
FILENAME_VALIDATION_PATTERN = re.compile(r"^[\w\-\.]+\.\w+$", re.IGNORECASE)

# Quick check pattern to fail fast on strings with no potential media
# ! = markdown image
# [ = markdown link
# I, V, A, P, D = WhatsApp filenames (IMG, VID, AUD, PTT, DOC)
# \u200e = Unicode marker
# ( = Attachment marker start (e.g., (file attached))
# < = Attachment marker start (e.g., <attached:)
QUICK_CHECK_PATTERN = re.compile(r"[!\[IVAPD\u200e(<]")
=======
FILENAME_LOOKBEHIND_PATTERN = re.compile(r"([\w\-\.]+\.\w+)\s*$", re.IGNORECASE)
>>>>>>> origin/pr/2707
=======
# Patterns for Markdown processing
# Kept for backward compatibility
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
>>>>>>> origin/pr/2706

COMBINED_MD_PATTERN = re.compile(
    r"""
    (?P<img_url>!\[[^\]]*\]\((?P<url1>[^)]+)\)) |
    (?P<link_url>(?<!!)\[[^\]]+\]\((?P<url2>[^)]+)\))
    """,
    re.VERBOSE,
)

# Note: _MARKERS_REGEX contains escaped strings (via re.escape), so spaces are escaped (e.g. '\ ').
# This is safe to use within re.VERBOSE where unescaped spaces are ignored.
COMBINED_RAW_PATTERN = re.compile(
    r"""
    (?P<att>(?i:(?P<att_file>[\w\-\.]+\.\w+)\s*(?:"""
    + _MARKERS_REGEX
    + r"""))) |
    (?P<wa>\b(?P<wa_file>(?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b) |
    (?P<uni>(?i:\u200e(?P<uni_file>(?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)))
    """,
    re.VERBOSE,
)


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


def find_all_media_references(text: str, *, include_uuids: bool = False) -> list[str]:
    """Find all media references using a single optimized regex pass.

    This combines:
    - Attachment markers
    - Markdown links/images (extracting filename)
    - WhatsApp patterns
    - Simple media filenames (e.g. foo.jpg)
    - UUID filenames (optional)

    Args:
        text: The message text to search.
        include_uuids: Whether to include UUID filenames (requires row['media_type'] check usually).

    Returns:
        List of unique media references found.

    """
    if not text:
        return []

    refs = set()
    for match in COMBINED_ENRICHMENT_PATTERN.finditer(text):
        name = match.lastgroup
        # Use lastgroup to identify which pattern matched
        if name == "md_file":
            refs.add(match.group("md_file"))
        elif name == "wa_file":
            refs.add(match.group("wa_file"))
        elif name == "uni_file":
            refs.add(match.group("uni_file"))
        elif name == "gen_file" or name == "gen_marker":
            filename = match.group("gen_file")
            # If marker matched, we always include it (legacy behavior for att_file)
            if match.group("gen_marker"):
                refs.add(filename)
            # Else check if it is a known media type
            elif detect_media_type(filename):
                refs.add(filename)
            # Else check if it is a UUID (if requested)
            elif include_uuids and UUID_VALIDATION_PATTERN.match(filename):
                refs.add(filename)

    return list(refs)


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
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        # Optimization: distinct messages to avoid redundant regex processing
        messages = df["text"].dropna().unique().tolist()
=======
        # Optimization: Avoid dropna() copy, handle None/NaN in loop
        messages = df["text"].tolist()
>>>>>>> origin/pr/2711
    elif hasattr(df, "to_pylist"):
        # pyarrow Table
        # Optimization: distinct messages to avoid redundant regex processing
        # Use column iterator to avoid full table conversion
        messages = list({x for x in df["text"].to_pylist() if x})
=======
        # Optimization: process only unique messages to avoid redundant regex scans.
        # Use dropna().unique() to exclude NaNs/Nones from the set.
        messages = df["text"].dropna().unique()
    elif hasattr(df, "to_pylist"):
        # pyarrow Table
        messages = {r["text"] for r in df.to_pylist() if r["text"] is not None}
>>>>>>> origin/pr/2712
=======
        # Optimization: distinct messages to avoid redundant regex processing
        messages = df["text"].dropna().unique().tolist()
    elif hasattr(df, "to_pylist"):
        # pyarrow Table
        messages = list({r["text"] for r in df.to_pylist() if r["text"]})
>>>>>>> origin/pr/2708
    else:
        # Fallback for unexpected type
        return references

<<<<<<< HEAD
    # Pre-bind regex methods for optimization
    fast_find = FAST_MEDIA_PATTERN.finditer
    marker_find = MARKER_PATTERN.finditer
<<<<<<< HEAD
    filename_match = FILENAME_VALIDATION_PATTERN.match
    quick_check = QUICK_CHECK_PATTERN.search
=======
    filename_search = FILENAME_LOOKBEHIND_PATTERN.search
>>>>>>> origin/pr/2707
=======
    # Pre-bind method for optimization
    md_find_iter = COMBINED_MD_PATTERN.finditer
    raw_find_iter = COMBINED_RAW_PATTERN.finditer
>>>>>>> origin/pr/2706

    for message in messages:
        if not message or not isinstance(message, str):
            continue

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        # Optimization: Fail fast if no potential media indicators are present
        if not quick_check(message):
            continue

        # Pass 1: Fast patterns (Images, Links, WhatsApp, Unicode)
        for match in fast_find(message):
<<<<<<< HEAD
=======
        for match in combined_find(message):
>>>>>>> origin/pr/2708
            # Optimization: Use lastgroup to avoid checking all groups
            group_name = match.lastgroup
            val = match.group(group_name)

<<<<<<< HEAD
            if group_name == "img_url":
                references.add(val)
            elif group_name == "link_url":
                if not val.startswith(("http://", "https://")):
                    references.add(val)
            elif group_name == "wa_file":
                references.add(val)
            elif group_name == "uni_file":
                references.add(val)
=======
            # Optimization: Use match.lastgroup for O(1) dispatch instead of checking all groups
            group_name = match.lastgroup
            if group_name == "img_url":
                references.add(match.group("img_url"))
            elif group_name == "link_url":
                link_url = match.group("link_url")
                if not link_url.startswith(("http://", "https://")):
                    references.add(link_url)
            elif group_name == "wa_file":
                references.add(match.group("wa_file"))
            elif group_name == "uni_file":
                references.add(match.group("uni_file"))
>>>>>>> origin/pr/2711

        # Pass 2: Attachments via markers (optimized to avoid greedy filename scanning)
        for match in marker_find(message):
            start_pos = match.start()
            lookback_slice = message[:start_pos]
            if not lookback_slice:
                continue

            # Optimized lookbehind:
            # Instead of a greedy regex searching from the end of the string (O(N)),
            # we manually split the string to find the last token and validate it.
            # This is ~5000x faster for long strings.

            # Remove trailing whitespace (spaces between filename and marker)
            lookback_stripped = lookback_slice.rstrip()
            if not lookback_stripped:
                continue

            # Get the last word/token
            # rsplit(None, 1) splits on whitespace from the right, max 1 split
            parts = lookback_stripped.rsplit(None, 1)
            candidate = parts[-1]

            # Validate the candidate against the allowed filename characters
            if filename_match(candidate):
                references.add(candidate)
=======
            # Specific validation for markdown links
            if group_name == "link_url" and val.startswith(("http://", "https://")):
                continue

            references.add(val)
>>>>>>> origin/pr/2708
=======
        # Pass 1: Fast patterns (Images, Links, WhatsApp, Unicode)
        for match in fast_find(message):
            if img_url := match.group("img_url"):
                references.add(img_url)
            elif link_url := match.group("link_url"):
                if not link_url.startswith(("http://", "https://")):
                    references.add(link_url)
            elif wa_file := match.group("wa_file"):
                references.add(wa_file)
            elif uni_file := match.group("uni_file"):
                references.add(uni_file)
>>>>>>> origin/pr/2707

        # Pass 2: Attachments via markers (optimized to avoid greedy filename scanning)
        for match in marker_find(message):
            start_pos = match.start()
            lookback_slice = message[:start_pos]
            if not lookback_slice:
                continue

            # Look for filename at the end of the preceding text
            if fm := filename_search(lookback_slice):
                references.add(fm.group(1))
=======
        # 1. Markdown references
        for match in md_find_iter(message):
            if match.group("url1"):
                references.add(match.group("url1"))
            elif match.group("url2"):
                ref = match.group("url2")
                if not ref.startswith(("http://", "https://")):
                    references.add(ref)

        # 2. Raw references
        for match in raw_find_iter(message):
            if match.group("att_file"):
                references.add(match.group("att_file"))
            elif match.group("wa_file"):
                references.add(match.group("wa_file"))
            elif match.group("uni_file"):
                references.add(match.group("uni_file"))
>>>>>>> origin/pr/2706

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
