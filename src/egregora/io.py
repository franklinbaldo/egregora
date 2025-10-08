"""Input/output and file system utilities."""

from __future__ import annotations

import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence, Dict

from .config import PipelineConfig
from .media_extractor import MediaFile, MediaExtractor

DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def find_date_in_name(path: Path) -> date | None:
    """Return the first YYYY-MM-DD date embedded in a filename."""
    match = DATE_IN_NAME_RE.search(path.name)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def list_zip_days(zips_dir: Path) -> list[tuple[date, Path]]:
    """Return available zip archives sorted by date."""
    zips: list[tuple[date, Path]] = []
    for path in zips_dir.glob("*.zip"):
        found_date = find_date_in_name(path)
        if found_date is not None:
            zips.append((found_date, path))
    zips.sort(key=lambda item: item[0])
    return zips


def select_recent_archives(
    archives: Sequence[tuple[date, Path]], *, days: int
) -> list[tuple[date, Path]]:
    """Select the most recent archives respecting *days*."""
    if days <= 0:
        raise ValueError("days must be positive")
    return list(archives[-days:]) if len(archives) >= days else list(archives)


def load_previous_newsletter(
    news_dir: Path, reference_date: date
) -> tuple[Path, str | None]:
    """Load yesterday's newsletter if it exists."""
    yesterday = reference_date - timedelta(days=1)
    path = news_dir / f"{yesterday.isoformat()}.md"
    if path.exists():
        return path, path.read_text(encoding="utf-8")
    return path, None


def ensure_directories(config: PipelineConfig) -> None:
    """Ensure required directories exist."""
    config.newsletters_dir.mkdir(parents=True, exist_ok=True)
    config.zips_dir.mkdir(parents=True, exist_ok=True)


def read_zip_texts_and_media(
    zippath: Path,
    *,
    archive_date: date | None = None,
    newsletters_dir: Path | None = None,
    group_slug: str | None = None,
) -> tuple[str, dict[str, MediaFile]]:
    """Read texts from *zippath* and optionally extract media files."""
    extractor: MediaExtractor | None = None
    media_files: dict[str, MediaFile] = {}

    if archive_date is not None:
        if (newsletters_dir is None) != (group_slug is None):
            raise ValueError(
                "newsletters_dir and group_slug must both be provided to extract media",
            )
        if newsletters_dir is not None and group_slug is not None:
            group_dir = newsletters_dir / group_slug
            extractor = MediaExtractor(group_dir, group_slug=group_slug)
            media_files = extractor.extract_media_from_zip(zippath, archive_date)

    chunks: list[str] = []
    with zipfile.ZipFile(zippath, "r") as zipped:
        txt_names = sorted(
            name for name in zipped.namelist() if name.lower().endswith(".txt")
        )
        for name in txt_names:
            with zipped.open(name, "r") as file_handle:
                raw = file_handle.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            text = text.replace("\r\n", "\n")
            chunks.append(f"\n# Arquivo: {name}\n{text.strip()}\n")

    transcript = "\n".join(chunks).strip()
    if extractor is not None and transcript:
        transcript = MediaExtractor.replace_media_references(transcript, media_files)

    return transcript, media_files


__all__ = [
    "find_date_in_name",
    "list_zip_days",
    "select_recent_archives",
    "load_previous_newsletter",
    "ensure_directories",
    "read_zip_texts_and_media",
]