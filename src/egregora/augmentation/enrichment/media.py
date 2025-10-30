"""Media extraction and replacement utilities for enrichment."""

import hashlib
import os
import re
import uuid
import zipfile
from pathlib import Path

import ibis
from ibis.expr.types import Table

from ...config import MEDIA_DIR_NAME

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

# URL extraction pattern
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text."""
    if not text:
        return []
    return URL_PATTERN.findall(text)


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
