"""Utilities for extracting and referencing WhatsApp media files."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

import polars as pl

from .types import GroupSlug

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

MEDIA_SUFFIX_MIN_PARTS = 2


@dataclass(slots=True)
class MediaFile:
    """Represents a media file extracted from a WhatsApp export."""

    filename: str
    media_type: str
    source_path: str
    dest_path: Path
    relative_path: str
    caption: str | None = None


class MediaExtractor:
    """Extracts WhatsApp media files and rewrites transcript references."""

    _ATTACHMENT_MARKERS = (
        "(arquivo anexado)",
        "(file attached)",
        "(archivo adjunto)",
    )
    _DEFAULT_ATTACHMENT_LABEL = "(arquivo anexado)"
    _DIRECTIONAL_TRANSLATION = str.maketrans("", "", "\u200e\u200f\u202a\u202b\u202c\u202d\u202e")
    _attachment_pattern = re.compile(
        r"[^\n]*?(?:"
        + "|".join(re.escape(marker) for marker in _ATTACHMENT_MARKERS)
        + ")",
        re.IGNORECASE,
    )

    def __init__(self, group_dir: Path, *, group_slug: GroupSlug | None = None) -> None:
        self.group_dir = group_dir
        self.group_dir.mkdir(parents=True, exist_ok=True)

        raw_slug = group_slug or "shared"
        slug = str(raw_slug).strip() or "shared"
        self.group_slug: GroupSlug = GroupSlug(slug)

        self.media_base_dir = self.group_dir / "media"
        self.media_base_dir.mkdir(parents=True, exist_ok=True)

        self._relative_root = self.group_dir.parent

    def extract_specific_media_from_zip(
        self,
        zip_path: Path,
        post_date: date,
        filenames: Iterable[str],
    ) -> dict[str, MediaFile]:
        """Extract only ``filenames`` from *zip_path* into ``post_date`` directory."""

        extracted: dict[str, MediaFile] = {}
        target_dir = self.media_base_dir

        cleaned_targets = {self._clean_attachment_name(name): name for name in filenames if name}
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
    ) -> dict[str, MediaFile]:
        """Extract all recognised media files from *zip_path*."""

        with zipfile.ZipFile(zip_path, "r") as zipped:
            filenames = [
                Path(info.filename).name
                for info in zipped.infolist()
                if not info.is_dir()
                and self._detect_media_type(self._clean_attachment_name(Path(info.filename).name))
            ]

        return self.extract_specific_media_from_zip(
            zip_path,
            post_date,
            filenames,
        )

    def _detect_media_type(self, filename: str) -> str | None:
        extension = Path(filename).suffix.lower()
        return MEDIA_TYPE_BY_EXTENSION.get(extension)

    @classmethod
    def replace_media_references_dataframe(
        cls,
        df: pl.DataFrame,
        media_files: dict[str, MediaFile],
        *,
        public_paths: dict[str, str] | None = None,
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
                segment = match.group(0)
                extracted = cls._extract_attachment_segment(segment)
                if extracted is None:
                    return segment

                sanitized_name, original_segment, marker_text = extracted
                key, media = cls._lookup_media(sanitized_name, media_files)
                if media is None:
                    return segment

                path = paths.get(key) if key and key in paths else None
                if path is None:
                    path = media.relative_path

                markdown = cls._format_markdown_reference(media, path)
                marker_display = marker_text.strip() or cls._DEFAULT_ATTACHMENT_LABEL
                return segment.replace(original_segment, f"{markdown} _{marker_display}_")

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
        media_files: dict[str, MediaFile],
        *,
        public_paths: dict[str, str] | None = None,
    ) -> str:
        """Return ``text`` with attachment markers replaced by Markdown links."""

        if not text or not media_files:
            return text

        paths = public_paths or cls.build_public_paths(media_files)
        pattern = cls._attachment_pattern

        def replacement(match: re.Match[str]) -> str:
            segment = match.group(0)
            extracted = cls._extract_attachment_segment(segment)
            if extracted is None:
                return segment

            sanitized_name, original_segment, marker_text = extracted
            key, media = cls._lookup_media(sanitized_name, media_files)
            if media is None:
                return segment

            path = paths.get(key) if key and key in paths else media.relative_path
            markdown = cls._format_markdown_reference(media, path)
            marker_display = marker_text.strip() or cls._DEFAULT_ATTACHMENT_LABEL
            return segment.replace(original_segment, f"{markdown} _{marker_display}_")

        return pattern.sub(replacement, text)

    @classmethod
    def find_attachment_names_dataframe(cls, df: pl.DataFrame) -> set[str]:
        """Return attachment names referenced inside a Polars ``DataFrame``."""

        if df.is_empty():
            return set()

        frame = df
        if "time" not in frame.columns:
            frame = frame.with_columns(pl.col("timestamp").dt.strftime("%H:%M").alias("time"))
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
                sanitized_name, _, _ = extracted
                if sanitized_name:
                    attachments.add(sanitized_name)
        return attachments

    @staticmethod
    def format_media_section(
        media_files: dict[str, MediaFile],
        *,
        public_paths: dict[str, str] | None = None,
    ) -> str | None:
        """Return a Markdown bullet list describing the shared media."""

        if not media_files:
            return None

        lines: list[str] = []
        for key in sorted(media_files):
            media = media_files[key]
            label = media.caption or media.filename
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
        media_files: dict[str, MediaFile],
        *,
        relative_to: Path | None = None,
        url_prefix: str | None = None,
    ) -> dict[str, str]:
        """Return paths suitable for linking from a post."""

        if not media_files:
            return {}

        results: dict[str, str] = {}

        if url_prefix:
            absolute = url_prefix.startswith("/")
            cleaned_prefix = url_prefix.strip("/")
            prefix_path = PurePosixPath(cleaned_prefix) if cleaned_prefix else None

            for key, media in media_files.items():
                suffix_parts = list(PurePosixPath(media.relative_path).parts)
                if suffix_parts and suffix_parts[0] in {"data", "posts"}:
                    suffix_parts = suffix_parts[1:]
                if len(suffix_parts) >= MEDIA_SUFFIX_MIN_PARTS and suffix_parts[1] == "media":
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
        filename: str, media_files: dict[str, MediaFile]
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
        label = media.caption or media.filename
        if media.media_type == "image":
            return f"![{label}]({path})"
        if media.media_type == "video":
            return f"[🎥 {label}]({path})"
        if media.media_type == "audio":
            return f"[🔊 {label}]({path})"
        if media.media_type == "document":
            return f"[📄 {label}]({path})"
        return f"[{label}]({path})"

    @classmethod
    def _clean_attachment_name(cls, filename: str) -> str:
        cleaned = filename.translate(cls._DIRECTIONAL_TRANSLATION)
        return cleaned.strip()

    @classmethod
    def _extract_attachment_segment(cls, line: str) -> tuple[str, str, str] | None:
        lowered = line.casefold()
        for marker in cls._ATTACHMENT_MARKERS:
            marker_lower = marker.casefold()
            idx = lowered.find(marker_lower)
            if idx == -1:
                continue

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
                sanitized = raw_name.strip()

            if not sanitized:
                return None

            original_segment = f"{raw_name} {suffix}" if raw_name else suffix
            return sanitized, original_segment, suffix
        return None
