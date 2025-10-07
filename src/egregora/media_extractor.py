"""Utilities for extracting and referencing WhatsApp media files."""

from __future__ import annotations

import os
import re
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable

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
    _directional_marks = re.compile(r"[\u200e\u200f\u202a-\u202e]")

    def __init__(self, media_base_dir: Path) -> None:
        self.media_base_dir = media_base_dir
        self.media_base_dir.mkdir(parents=True, exist_ok=True)

    def extract_specific_media_from_zip(
        self,
        zip_path: Path,
        newsletter_date: date,
        filenames: Iterable[str],
        *,
        group_slug: str | None = None,
    ) -> Dict[str, MediaFile]:
        """Extract only ``filenames`` from *zip_path* into ``newsletter_date`` directory."""

        cleaned_targets = {
            self._clean_attachment_name(name): name for name in filenames if name
        }
        if not cleaned_targets:
            return {}

        extracted: Dict[str, MediaFile] = {}
        group_key = (group_slug or "shared").strip() or "shared"
        target_dir = self.media_base_dir / group_key / "media"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Create a stable namespace for this group to generate deterministic UUIDs
        namespace = uuid.uuid5(uuid.NAMESPACE_DNS, group_key)

        with zipfile.ZipFile(zip_path, "r") as zipped:
            for info in zipped.infolist():
                if info.is_dir():
                    continue

                original_name = Path(info.filename).name
                cleaned_name = self._clean_attachment_name(original_name)
                if cleaned_name not in cleaned_targets:
                    continue

                media_type = self._detect_media_type(cleaned_name)
                if media_type is None:
                    continue

                if cleaned_name in extracted:
                    continue

                # Generate a deterministic UUID for the filename
                file_uuid = uuid.uuid5(namespace, cleaned_name)
                file_extension = Path(cleaned_name).suffix
                new_filename = f"{file_uuid}{file_extension}"
                dest_path = target_dir / new_filename

                if not dest_path.exists():
                    with zipped.open(info, "r") as source, open(
                        dest_path, "wb"
                    ) as target:
                        shutil.copyfileobj(source, target)

                relative_path = str(
                    Path("data") / "media" / group_key / "media" / new_filename
                )
                extracted[cleaned_name] = MediaFile(
                    filename=new_filename,
                    media_type=media_type,
                    source_path=info.filename,
                    dest_path=dest_path,
                    relative_path=relative_path,
                )

        return extracted

    def extract_media_from_zip(
        self,
        zip_path: Path,
        newsletter_date: date,
        *,
        group_slug: str | None = None,
    ) -> Dict[str, MediaFile]:
        """Extract all recognised media files from *zip_path*."""

        with zipfile.ZipFile(zip_path, "r") as zipped:
            filenames = [
                Path(info.filename).name
                for info in zipped.infolist()
                if not info.is_dir()
                and self._detect_media_type(
                    self._clean_attachment_name(Path(info.filename).name)
                )
            ]

        return self.extract_specific_media_from_zip(
            zip_path,
            newsletter_date,
            filenames,
            group_slug=group_slug,
        )

    def _detect_media_type(self, filename: str) -> str | None:
        extension = Path(filename).suffix.lower()
        return MEDIA_TYPE_BY_EXTENSION.get(extension)

    @staticmethod
    def replace_media_references(
        text: str,
        media_files: Dict[str, MediaFile],
        *,
        public_paths: Dict[str, str] | None = None,
    ) -> str:
        """Replace WhatsApp attachment markers with Markdown references."""

        if not media_files:
            return text

        def replacement(match: re.Match[str]) -> str:
            raw_name = match.group(1).strip()
            media = MediaExtractor._lookup_media(raw_name, media_files)
            if media is None:
                return match.group(0)

            canonical = MediaExtractor._clean_attachment_name(media.filename)
            path = (
                public_paths.get(canonical)
                if public_paths and canonical in public_paths
                else media.relative_path
            )

            markdown = MediaExtractor._format_markdown_reference(media, path)
            return f"{markdown} _(arquivo anexado)_"

        return MediaExtractor._attachment_pattern.sub(replacement, text)

    @classmethod
    def find_attachment_names(cls, text: str) -> set[str]:
        """Return sanitized attachment filenames referenced in *text*."""

        return {
            cls._clean_attachment_name(match.group(1).strip())
            for match in cls._attachment_pattern.finditer(text)
        }

    @staticmethod
    def format_media_section(
        media_files: Dict[str, MediaFile],
        *,
        public_paths: Dict[str, str] | None = None,
    ) -> str | None:
        """Return a Markdown bullet list describing the shared media."""

        if not media_files:
            return None

        lines: list[str] = []
        for key in sorted(media_files):
            media = media_files[key]
            label = media.filename
            path = (
                public_paths.get(key)
                if public_paths and key in public_paths
                else media.relative_path
            )
            if media.media_type == "image":
                rendered = f"![{label}]({path})"
            elif media.media_type == "video":
                rendered = f"[🎥 {label}]({path})"
            elif media.media_type == "audio":
                rendered = f"[🔊 {label}]({path})"
            elif media.media_type == "document":
                rendered = f"[📄 {label}]({path})"
            else:
                rendered = f"[{label}]({path})"
            lines.append(f"- {rendered}")

        return "\n".join(lines)

    @staticmethod
    def build_public_paths(
        media_files: Dict[str, MediaFile],
        *,
        relative_to: Path | None = None,
        url_prefix: str | None = None,
    ) -> Dict[str, str]:
        """Return paths suitable for linking from a newsletter."""

        if not media_files:
            return {}

        results: Dict[str, str] = {}

        if url_prefix:
            absolute = url_prefix.startswith("/")
            cleaned_prefix = url_prefix.strip("/")
            prefix_path = PurePosixPath(cleaned_prefix) if cleaned_prefix else None

            for key, media in media_files.items():
                suffix_parts = list(PurePosixPath(media.relative_path).parts)
                if suffix_parts and suffix_parts[0] == "data":
                    suffix_parts = suffix_parts[1:]
                if suffix_parts and suffix_parts[0] == "media":
                    suffix_parts = suffix_parts[1:]
                suffix = PurePosixPath(*suffix_parts)
                if prefix_path is not None:
                    combined = prefix_path.joinpath(suffix)
                else:
                    combined = suffix
                path = combined.as_posix()
                results[key] = f"/{path}" if absolute else path
            return results

        if relative_to is not None:
            base_dir = Path(relative_to)
            for key, media in media_files.items():
                rel_path = os.path.relpath(media.dest_path, base_dir)
                results[key] = PurePosixPath(rel_path).as_posix()
            return results

        for key, media in media_files.items():
            results[key] = media.relative_path

        return results

    @staticmethod
    def _lookup_media(filename: str, media_files: Dict[str, MediaFile]) -> MediaFile | None:
        canonical = MediaExtractor._clean_attachment_name(Path(filename).name)
        if canonical in media_files:
            return media_files[canonical]

        lowercase = canonical.lower()
        for key, media in media_files.items():
            candidate = MediaExtractor._clean_attachment_name(Path(key).name)
            if candidate.lower() == lowercase or media.filename.lower() == lowercase:
                return media
        return None

    @staticmethod
    def _format_markdown_reference(media: MediaFile, path: str) -> str:
        if media.media_type == "image":
            return f"![{media.filename}]({path})"
        if media.media_type == "video":
            return f"[🎥 {media.filename}]({path})"
        if media.media_type == "audio":
            return f"[🔊 {media.filename}]({path})"
        if media.media_type == "document":
            return f"[📄 {media.filename}]({path})"
        return f"[{media.filename}]({path})"

    @classmethod
    def _clean_attachment_name(cls, filename: str) -> str:
        cleaned = cls._directional_marks.sub("", filename)
        return cleaned.strip()
