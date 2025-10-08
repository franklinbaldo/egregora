"""Utilities for extracting and referencing WhatsApp media files."""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable

import polars as pl

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

    _ATTACHMENT_MARKER = "(arquivo anexado)"
    _DIRECTIONAL_TRANSLATION = str.maketrans("", "", "\u200e\u200f\u202a\u202b\u202c\u202d\u202e")

    def __init__(self, group_dir: Path, *, group_slug: str | None = None) -> None:
        self.group_dir = group_dir
        self.group_dir.mkdir(parents=True, exist_ok=True)

        slug = (group_slug or "shared").strip() or "shared"
        self.group_slug = slug

        self.media_base_dir = self.group_dir / "media"
        self.media_base_dir.mkdir(parents=True, exist_ok=True)

        self._relative_root = self.group_dir.parent

    def extract_specific_media_from_zip(
        self,
        zip_path: Path,
        post_date: date,
        filenames: Iterable[str],
    ) -> Dict[str, MediaFile]:
        """Extract only ``filenames`` from *zip_path* into ``post_date`` directory."""

        extracted: Dict[str, MediaFile] = {}
        target_dir = self.media_base_dir

        cleaned_targets = {
            self._clean_attachment_name(name): name for name in filenames if name
        }
        if not cleaned_targets:
            return {}

        # Create a stable namespace for this group to generate deterministic UUIDs
        namespace = uuid.uuid5(uuid.NAMESPACE_DNS, self.group_slug)

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

                # Generate a deterministic UUID based on file content to avoid collisions
                with zipped.open(info, "r") as source:
                    file_content = source.read()

                content_hash = hashlib.sha256(file_content).hexdigest()
                file_uuid = uuid.uuid5(namespace, content_hash)
                file_extension = Path(cleaned_name).suffix
                new_filename = f"{file_uuid}{file_extension}"
                dest_path = target_dir / new_filename

                if not dest_path.exists():
                    with open(dest_path, "wb") as target:
                        target.write(file_content)

                relative_path = PurePosixPath(
                    os.path.relpath(dest_path, self._relative_root)
                ).as_posix()
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
        post_date: date,
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
            post_date,
            filenames,
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

        lines: list[str] = []
        for raw_line in text.splitlines(keepends=True):
            if raw_line.endswith("\n"):
                line = raw_line[:-1]
                newline = "\n"
            else:
                line = raw_line
                newline = ""

            extracted = MediaExtractor._extract_attachment_segment(line)
            if extracted is None:
                lines.append(raw_line)
                continue

            sanitized_name, original_segment = extracted
            key, media = MediaExtractor._lookup_media(sanitized_name, media_files)
            if media is None:
                lines.append(raw_line)
                continue

            path = (
                public_paths.get(key)
                if public_paths and key in public_paths
                else media.relative_path
            )

            markdown = MediaExtractor._format_markdown_reference(media, path)
            replaced = line.replace(
                original_segment,
                f"{markdown} _(arquivo anexado)_",
            )
            lines.append(replaced + newline)

        return "".join(lines)

    @classmethod
    def replace_media_references_dataframe(
        cls,
        df: pl.DataFrame,
        media_files: Dict[str, MediaFile],
        *,
        public_paths: Dict[str, str] | None = None,
        column: str | None = None,
    ) -> pl.DataFrame:
        """Return a DataFrame with attachment markers expanded in ``column``."""

        if not media_files or df.is_empty():
            return df.clone()

        target_column = column
        if target_column is None:
            if "tagged_line" in df.columns:
                tagged_has_content = bool(
                    df.select(pl.col("tagged_line").is_not_null().any()).item()
                )
                if tagged_has_content:
                    target_column = "tagged_line"
                elif "original_line" in df.columns:
                    target_column = "original_line"
                else:
                    target_column = "tagged_line"
            elif "original_line" in df.columns:
                target_column = "original_line"
            else:
                target_column = "message"

        if target_column not in df.columns:
            raise KeyError(f"Column '{target_column}' not found in DataFrame")

        paths = public_paths or cls.build_public_paths(media_files)
        pattern = cls._attachment_pattern

        def _replace(text: str | None) -> str:
            if not text:
                return ""

            def replacement(match: re.Match[str]) -> str:
                raw_name = match.group(1).strip()
                key, media = cls._lookup_media(raw_name, media_files)
                if media is None:
                    return match.group(0)

                path = paths.get(key) if key and key in paths else None
                if path is None:
                    path = media.relative_path

                markdown = cls._format_markdown_reference(media, path)
                return f"{markdown} _(arquivo anexado)_"

            return pattern.sub(replacement, text)

        return df.with_columns(
            pl.col(target_column)
            .cast(pl.String)
            .map_elements(_replace, return_dtype=pl.String)
            .alias(target_column)
        )

    @classmethod
    def replace_media_references(
        cls,
        text: str,
        media_files: Dict[str, MediaFile],
        *,
        public_paths: Dict[str, str] | None = None,
    ) -> str:
        """Return ``text`` with attachment markers replaced by Markdown links."""

        if not text or not media_files:
            return text

        paths = public_paths or cls.build_public_paths(media_files)
        pattern = cls._attachment_pattern

        def replacement(match: re.Match[str]) -> str:
            raw_name = match.group(1).strip()
            key, media = cls._lookup_media(raw_name, media_files)
            if media is None:
                return match.group(0)

            path = paths.get(key) if key and key in paths else media.relative_path
            markdown = cls._format_markdown_reference(media, path)
            return f"{markdown} _(arquivo anexado)_"

        return pattern.sub(replacement, text)
        attachments: set[str] = set()
        for line in text.splitlines():
            extracted = cls._extract_attachment_segment(line)
            if extracted is None:
                continue
            sanitized_name, _ = extracted
            if sanitized_name:
                attachments.add(sanitized_name)
        return attachments

    @classmethod
    def find_attachment_names_dataframe(cls, df: pl.DataFrame) -> set[str]:
        """Return attachment names referenced inside a Polars ``DataFrame``."""

        if df.is_empty():
            return set()

        frame = df
        if "time" not in frame.columns:
            frame = frame.with_columns(
                pl.col("timestamp").dt.strftime("%H:%M").alias("time")
            )
        time_expr = (
            pl.when(pl.col("time").is_not_null())
            .then(pl.col("time"))
            .otherwise(pl.col("timestamp").dt.strftime("%H:%M"))
        )
        author_expr = pl.col("author").fill_null("")
        message_expr = pl.col("message").fill_null("")
        fallback = pl.format("{} — {}: {}", time_expr, author_expr, message_expr)

        candidates: list[pl.Expr] = [fallback]

        if "original_line" in frame.columns:
            candidates.insert(
                0,
                pl.when(
                    pl.col("original_line").is_not_null()
                    & (pl.col("original_line").str.len_chars() > 0)
                )
                .then(pl.col("original_line"))
                .otherwise(None),
            )

        if "tagged_line" in frame.columns:
            candidates.insert(
                0,
                pl.when(
                    pl.col("tagged_line").is_not_null()
                    & (pl.col("tagged_line").str.len_chars() > 0)
                )
                .then(pl.col("tagged_line"))
                .otherwise(None),
            )

        lines = frame.with_columns(pl.coalesce(*candidates).alias("__line"))

        attachments: set[str] = set()
        for value in lines.get_column("__line").to_list():
            if not isinstance(value, str):
                continue
            for part in value.splitlines():
                extracted = cls._extract_attachment_segment(part)
                if extracted is None:
                    continue
                sanitized_name, _ = extracted
                if sanitized_name:
                    attachments.add(sanitized_name)
        return attachments

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
        """Return paths suitable for linking from a post."""

        if not media_files:
            return {}

        results: Dict[str, str] = {}

        if url_prefix:
            absolute = url_prefix.startswith("/")
            cleaned_prefix = url_prefix.strip("/")
            prefix_path = PurePosixPath(cleaned_prefix) if cleaned_prefix else None

            for key, media in media_files.items():
                suffix_parts = list(PurePosixPath(media.relative_path).parts)
                if suffix_parts and suffix_parts[0] in {"data", "posts"}:
                    suffix_parts = suffix_parts[1:]
                if len(suffix_parts) >= 2 and suffix_parts[1] == "media":
                    suffix_parts = [suffix_parts[0], *suffix_parts[2:]]
                suffix = PurePosixPath(*suffix_parts)
                combined = prefix_path.joinpath(suffix) if prefix_path else suffix
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
    def _lookup_media(
        filename: str, media_files: Dict[str, MediaFile]
    ) -> tuple[str | None, MediaFile | None]:
        """Find a media file by its original name, returning the key and the file."""
        canonical = MediaExtractor._clean_attachment_name(Path(filename).name)
        if canonical in media_files:
            return canonical, media_files[canonical]

        lowercase = canonical.lower()
        for key, media in media_files.items():
            candidate = MediaExtractor._clean_attachment_name(Path(key).name)
            if candidate.lower() == lowercase:
                return key, media
        return None, None

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
        cleaned = filename.translate(cls._DIRECTIONAL_TRANSLATION)
        return cleaned.strip()

    @classmethod
    def _extract_attachment_segment(cls, line: str) -> tuple[str, str] | None:
        lowered = line.casefold()
        marker = cls._ATTACHMENT_MARKER
        marker_lower = marker.casefold()
        idx = lowered.find(marker_lower)
        if idx == -1:
            return None

        suffix = line[idx : idx + len(marker)]
        prefix = line[:idx].rstrip()

        if ": " in prefix:
            _, candidate = prefix.rsplit(": ", 1)
        elif ":" in prefix:
            _, candidate = prefix.rsplit(":", 1)
        else:
            candidate = prefix

        raw_name = candidate.strip()
        sanitized = cls._clean_attachment_name(raw_name)
        if not sanitized:
            return None

        original_segment = f"{raw_name} {suffix}" if raw_name else suffix
        return sanitized, original_segment
