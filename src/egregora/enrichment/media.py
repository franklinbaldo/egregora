"""Media extraction and replacement utilities for enrichment."""

import hashlib
import os
import re
import uuid
import zipfile
from pathlib import Path
from typing import Annotated

import ibis
from ibis.expr.types import Table

from egregora.config import MEDIA_DIR_NAME
from egregora.enrichment.batch import _iter_table_record_batches

ATTACHMENT_MARKERS = ("(arquivo anexado)", "(file attached)", "(archivo adjunto)", "\u200e<attached:")
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
URL_PATTERN = re.compile('https?://[^\\s<>"{}|\\\\^`\\[\\]]+')


def extract_urls(
    text: Annotated[str, "The text to extract URLs from"],
) -> Annotated[list[str], "A list of URLs found in the text"]:
    """Extract all URLs from text."""
    if not text:
        return []
    return URL_PATTERN.findall(text)


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


def find_media_references(
    text: Annotated[str, "The message text to search for media references"],
) -> Annotated[list[str], "A list of media filenames found in the text"]:
    """Find media filenames in WhatsApp messages.

    WhatsApp marks media with special patterns like:
    - "IMG-20250101-WA0001.jpg (arquivo anexado)"
    - "<attached: IMG-20250101-WA0001.jpg>"
    """
    if not text:
        return []
    media_files = []
    for marker in ATTACHMENT_MARKERS:
        pattern = "([\\w\\-\\.]+\\.\\w+)\\s*" + re.escape(marker)
        matches = re.findall(pattern, text, re.IGNORECASE)
        media_files.extend(matches)
    wa_pattern = "\\b((?:IMG|VID|AUD|PTT|DOC)-\\d+-WA\\d+\\.\\w+)\\b"
    wa_matches = re.findall(wa_pattern, text)
    media_files.extend(wa_matches)
    return list(set(media_files))


def extract_media_from_zip(
    zip_path: Annotated[Path, "The path to the WhatsApp export ZIP file"],
    filenames: Annotated[set[str], "A set of media filenames to extract"],
    docs_dir: Annotated[Path, "The MkDocs docs directory"],
    group_slug: Annotated[str, "The slug of the WhatsApp group"],
) -> Annotated[dict[str, Path], "A mapping from original filenames to their new paths on disk"]:
    """Extract media files from ZIP and save to output_dir/media/.

    Returns dict mapping original filename to saved path.
    """
    if not filenames:
        return {}
    media_dir = docs_dir / MEDIA_DIR_NAME
    media_dir.mkdir(parents=True, exist_ok=True)
    namespace = uuid.uuid5(uuid.NAMESPACE_DNS, group_slug)
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


def replace_media_mentions(
    text: Annotated[str, "The message text to process"],
    media_mapping: Annotated[dict[str, Path], "A mapping from original filenames to their new paths on disk"],
    docs_dir: Annotated[Path, "The MkDocs docs directory"],
    posts_dir: Annotated[Path, "The directory where posts are stored"],
) -> Annotated[str, "The message text with media references replaced by markdown links"]:
    """Replace WhatsApp media filenames with new UUID5 paths.

    "Check this IMG-20250101-WA0001.jpg (file attached)"
    → "Check this ![Image](media/images/abc123def.jpg)"
    """
    if not text or not media_mapping:
        return text
    result = text
    for original_filename, new_path in media_mapping.items():
        try:
            relative_link = Path(os.path.relpath(new_path, posts_dir)).as_posix()
        except ValueError:
            try:
                relative_link = "/" + new_path.relative_to(docs_dir).as_posix()
            except ValueError:
                relative_link = new_path.as_posix()
        if not new_path.exists():
            replacement = "[Media removed: privacy protection]"
            for marker in ATTACHMENT_MARKERS:
                pattern = re.escape(original_filename) + "\\s*" + re.escape(marker)
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            result = re.sub("\\b" + re.escape(original_filename) + "\\b", replacement, result)
            image_pattern = "!\\[[^\\]]*\\]\\(" + re.escape(relative_link) + "\\)"
            result = re.sub(image_pattern, replacement, result)
            link_pattern = "\\[[^\\]]*\\]\\(" + re.escape(relative_link) + "\\)"
            result = re.sub(link_pattern, replacement, result)
            continue
        ext = new_path.suffix.lower()
        is_image = ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        replacement = f"![Image]({relative_link})" if is_image else f"[{new_path.name}]({relative_link})"
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(original_filename) + "\\s*" + re.escape(marker)
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        result = re.sub("\\b" + re.escape(original_filename) + "\\b", replacement, result)
    return result


def extract_and_replace_media(
    messages_table: Annotated[Table, "The table of messages to process"],
    zip_path: Annotated[Path, "The path to the WhatsApp export ZIP file"],
    docs_dir: Annotated[Path, "The MkDocs docs directory"],
    posts_dir: Annotated[Path, "The directory where posts are stored"],
    group_slug: Annotated[str, "The slug of the WhatsApp group"] = "shared",
) -> tuple[
    Annotated[Table, "The updated table with media references replaced"],
    Annotated[dict[str, Path], "A mapping from original filenames to their new paths on disk"],
]:
    """Extract media from ZIP and replace mentions in Table.

    Returns:
        - Updated Table with new media paths
        - Media mapping (original → extracted path)

    """
    all_media = set()
    batch_size = 1000
    for batch_records in _iter_table_record_batches(messages_table, batch_size):
        for row in batch_records:
            message = row.get("message", "")
            media_refs = find_media_references(message)
            all_media.update(media_refs)
    media_mapping = extract_media_from_zip(zip_path, all_media, docs_dir, group_slug)
    if not media_mapping:
        return (messages_table, {})

    @ibis.udf.scalar.python
    def replace_in_message(message: str) -> str:
        return replace_media_mentions(message, media_mapping, docs_dir, posts_dir) if message else message

    updated_table = messages_table.mutate(message=replace_in_message(messages_table.message))
    return (updated_table, media_mapping)


def detect_media_type(
    file_path: Annotated[Path, "The path to the media file"],
) -> Annotated[str | None, "The detected media type, or None if unknown"]:
    """Detect media type from file extension."""
    ext = file_path.suffix.lower()
    for extension, media_type in MEDIA_EXTENSIONS.items():
        if ext == extension:
            return media_type
    return None
