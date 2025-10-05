"""Core newsletter generation pipeline."""

from __future__ import annotations

import os
import re
import zipfile
from datetime import date, datetime, timedelta, tzinfo
from importlib import resources
from pathlib import Path
from typing import Any, Sequence

import logging

try:  # pragma: no cover - executed only when dependency is missing
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from .anonymizer import Anonymizer
from .config import PipelineConfig
from .media_extractor import MediaExtractor, MediaFile

DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _emit(
    message: str,
    *,
    logger: logging.Logger | None = None,
    batch_mode: bool = False,
    level: str = "info",
) -> None:
    """Emit a log message respecting batch execution preferences."""

    if logger is not None:
        log_func = getattr(logger, level, logger.info)
        log_func(message)
    elif not batch_mode:
        print(message)


TRANSCRIPT_PATTERNS = [
    re.compile(
        r"^(?P<prefix>\d{1,2}:\d{2}\s[-–—]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s[-–—]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\[\d{1,2}:\d{2}:\d{2}\]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[-–—]\s+)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
]

def _anonymize_transcript_line(
    line: str,
    *,
    anonymize: bool,
    format: str = "human",
) -> str:
    """Return ``line`` with the author anonymized when enabled."""

    if not anonymize:
        return line

    for pattern in TRANSCRIPT_PATTERNS:
        match = pattern.match(line)
        if not match:
            continue

        prefix = match.group("prefix")
        author = match.group("author").strip()
        separator = match.group("separator")
        message = match.group("message")

        if author:
            anonymized = Anonymizer.anonymize_author(author, format)
        else:
            anonymized = author

        return f"{prefix}{anonymized}{separator}{message}"

    return line


def _prepare_transcripts(
    transcripts: Sequence[tuple[date, str]],
    config: PipelineConfig,
    *,
    logger: logging.Logger | None = None,
    batch_mode: bool = False,
) -> list[tuple[date, str]]:
    """Return transcripts with authors anonymized when enabled."""

    sanitized: list[tuple[date, str]] = []
    anonymized_authors: set[str] = set()
    processed_lines = 0

    for transcript_date, raw_text in transcripts:
        if not config.anonymization.enabled or not raw_text:
            sanitized.append((transcript_date, raw_text))
            continue

        processed_parts: list[str] = []
        for raw_line in raw_text.splitlines(keepends=True):
            if raw_line.endswith("\n"):
                line = raw_line[:-1]
                newline = "\n"
            else:
                line = raw_line
                newline = ""

            anonymized = _anonymize_transcript_line(
                line,
                anonymize=config.anonymization.enabled,
                format=config.anonymization.output_format,
            )
            processed_parts.append(anonymized + newline)

            processed_lines += 1
            for pattern in TRANSCRIPT_PATTERNS:
                match = pattern.match(line)
                if not match:
                    continue

                author = match.group("author").strip()
                if author:
                    anonymized_authors.add(author)
                break

        sanitized.append((transcript_date, "".join(processed_parts)))

    if config.anonymization.enabled:
        _emit(
            "[Anonimização] "
            f"{len(anonymized_authors)} remetentes anonimizados em {processed_lines} linhas.",
            logger=logger,
            batch_mode=batch_mode,
        )

    return sanitized


def _prepare_transcripts_sample(
    transcripts: Sequence[tuple[date, str]],
    *,
    max_chars: int,
) -> str:
    """Concatenate recent transcripts limited to ``max_chars`` characters."""

    if max_chars <= 0:
        return ""

    ordered = sorted(transcripts, key=lambda item: item[0], reverse=True)
    collected: list[str] = []
    remaining = max_chars

    for _, text in ordered:
        snippet = text.strip()
        if not snippet:
            continue

        if len(snippet) > remaining:
            snippet = snippet[:remaining]
        collected.append(snippet)
        remaining -= len(snippet)
        if remaining <= 0:
            break

    return "\n\n".join(collected).strip()


def _require_google_dependency() -> None:
    """Ensure the optional google-genai dependency is available."""

    if genai is None or types is None:
        raise RuntimeError(
            "A dependência opcional 'google-genai' não está instalada. "
            "Instale-a para gerar newsletters (ex.: `pip install google-genai`)."
        )


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


def read_zip_texts_and_media(
    zippath: Path,
    *,
    archive_date: date | None = None,
    media_dir: Path | None = None,
) -> tuple[str, dict[str, MediaFile]]:
    """Read texts from *zippath* and optionally extract media files."""

    extractor: MediaExtractor | None = None
    media_files: dict[str, MediaFile] = {}

    if archive_date is not None and media_dir is not None:
        extractor = MediaExtractor(media_dir)
        media_files = extractor.extract_media_from_zip(zippath, archive_date)

    chunks: list[str] = []
    with zipfile.ZipFile(zippath, "r") as zipped:
        txt_names = sorted(name for name in zipped.namelist() if name.lower().endswith(".txt"))
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


def load_previous_newsletter(news_dir: Path, reference_date: date) -> tuple[Path, str | None]:
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
    config.media_dir.mkdir(parents=True, exist_ok=True)


def select_recent_archives(
    archives: Sequence[tuple[date, Path]], *, days: int
) -> list[tuple[date, Path]]:
    """Select the most recent archives respecting *days*."""

    if days <= 0:
        raise ValueError("days must be positive")
    return list(archives[-days:]) if len(archives) >= days else list(archives)


__all__ = [
    "ensure_directories",
    "find_date_in_name",
    "list_zip_days",
    "load_previous_newsletter",
    "read_zip_texts_and_media",
    "select_recent_archives",
    "_anonymize_transcript_line",
    "_prepare_transcripts",
    "_prepare_transcripts_sample",
]
