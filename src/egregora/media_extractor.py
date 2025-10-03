"""Utilities for extracting and referencing WhatsApp media files."""

from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict

MEDIA_TYPE_BY_EXTENSION = {
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
    ".mkv": "video",
    # Audio
    ".opus": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    ".wav": "audio",
    # Documents and others
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
    ".ppt": "document",
    ".pptx": "document",
    ".xls": "document",
    ".xlsx": "document",
    ".csv": "document",
    ".txt": "document",
    ".zip": "document",
}


@dataclass(slots=True)
class MediaFile:
    """Represents a media file extracted from a WhatsApp export."""

    filename: str
    media_type: str
    source_path: str
    dest_path: Path
    relative_path: str


class MediaExtractor:
    """Extracts WhatsApp media files and rewrites transcript references."""

    _attachment_pattern = re.compile(
        r"\u200e?([\w\-()\s]+?\.[a-z0-9]{1,6})\s*\(arquivo anexado\)",
        re.IGNORECASE,
    )

    def __init__(self, media_base_dir: Path) -> None:
        self.media_base_dir = media_base_dir
        self.media_base_dir.mkdir(parents=True, exist_ok=True)

    def extract_media_from_zip(
        self,
        zip_path: Path,
        newsletter_date: date,
    ) -> Dict[str, MediaFile]:
        """Extract supported media files from *zip_path* into a dated directory."""

        extracted: Dict[str, MediaFile] = {}
        target_dir = self.media_base_dir / newsletter_date.isoformat()
        target_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zipped:
            for info in zipped.infolist():
                if info.is_dir():
                    continue

                filename = Path(info.filename).name
                media_type = self._detect_media_type(filename)
                if media_type is None:
                    continue

                if filename in extracted:
                    continue

                dest_path, stored_name = self._resolve_destination(target_dir, filename)

                if not dest_path.exists():
                    with zipped.open(info, "r") as source, open(dest_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                relative_path = str(Path("media") / newsletter_date.isoformat() / stored_name)
                extracted[filename] = MediaFile(
                    filename=stored_name,
                    media_type=media_type,
                    source_path=info.filename,
                    dest_path=dest_path,
                    relative_path=relative_path,
                )

        return extracted

    def _detect_media_type(self, filename: str) -> str | None:
        extension = Path(filename).suffix.lower()
        return MEDIA_TYPE_BY_EXTENSION.get(extension)

    @staticmethod
    def replace_media_references(text: str, media_files: Dict[str, MediaFile]) -> str:
        """Replace WhatsApp attachment markers with Markdown references."""

        if not media_files:
            return text

        def replacement(match: re.Match[str]) -> str:
            raw_name = match.group(1).strip()
            media = MediaExtractor._lookup_media(raw_name, media_files)
            if media is None:
                return match.group(0)

            markdown = MediaExtractor._format_markdown_reference(media)
            return f"{markdown} _(arquivo anexado)_"

        return MediaExtractor._attachment_pattern.sub(replacement, text)

    @staticmethod
    def _lookup_media(filename: str, media_files: Dict[str, MediaFile]) -> MediaFile | None:
        canonical = Path(filename).name
        if canonical in media_files:
            return media_files[canonical]

        lowercase = canonical.lower()
        for key, media in media_files.items():
            if Path(key).name.lower() == lowercase:
                return media
            if media.filename.lower() == lowercase:
                return media
        return None

    @staticmethod
    def _format_markdown_reference(media: MediaFile) -> str:
        if media.media_type == "image":
            return f"![{media.filename}]({media.relative_path})"
        if media.media_type == "video":
            return f"[🎥 {media.filename}]({media.relative_path})"
        if media.media_type == "audio":
            return f"[🔊 {media.filename}]({media.relative_path})"
        if media.media_type == "document":
            return f"[📄 {media.filename}]({media.relative_path})"
        return f"[{media.filename}]({media.relative_path})"

    @staticmethod
    def _resolve_destination(directory: Path, filename: str) -> tuple[Path, str]:
        base_path = directory / filename
        if not base_path.exists():
            return base_path, filename

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 2
        while True:
            candidate_name = f"{stem}-{counter}{suffix}"
            candidate_path = directory / candidate_name
            if not candidate_path.exists():
                return candidate_path, candidate_name
            counter += 1
