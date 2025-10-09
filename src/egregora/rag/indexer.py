"""Utilities for building and updating the local post index."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator, Sequence
from datetime import date
from pathlib import Path

HEADER_RE = re.compile(r"^(?P<level>#+)\s+(?P<title>.+)$")
DATE_IN_STEM_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _extract_iso_date(raw_value: str) -> date | None:
    """Parse an ISO date embedded in *raw_value* if present."""

    match = DATE_IN_STEM_RE.search(raw_value)
    if not match:
        return None

    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def detect_post_date(path: Path) -> date | None:
    """Return the date encoded in a post file name, if present."""

    return _extract_iso_date(path.stem)


def detect_newsletter_date(path: Path) -> date | None:
    """Return the date embedded in newsletter paths (file or parent folders)."""

    if date_match := _extract_iso_date(path.stem):
        return date_match

    for parent in path.parents:
        if parent.name:
            date_match = _extract_iso_date(parent.name)
            if date_match:
                return date_match

    return None


def hash_text(text: str) -> str:
    """Return a stable hash for *text* used to detect modifications."""

    digest = hashlib.sha256()
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def iter_sections(text: str) -> Iterator[tuple[str | None, str]]:
    """Yield ``(title, section_text)`` pairs from the markdown *text*."""

    current_title: str | None = None
    collected: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = HEADER_RE.match(line)
        if match:
            if collected:
                section = "\n".join(collected).strip()
                if section:
                    yield current_title, section
                collected.clear()
            current_title = match.group("title").strip()
            continue

        collected.append(line)

    if collected:
        section = "\n".join(collected).strip()
        if section:
            yield current_title, section


def _chunk_paragraphs(
    paragraphs: Sequence[str], *, chunk_chars: int, overlap_chars: int
) -> Iterator[str]:
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be zero or positive")

    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        stripped = paragraph.strip()
        if not stripped:
            continue

        if current and current_len + len(stripped) > chunk_chars:
            yield "\n\n".join(current).strip()

            if overlap_chars:
                retained: list[str] = []
                retained_len = 0
                for part in reversed(current):
                    retained.append(part)
                    retained_len += len(part)
                    if retained_len >= overlap_chars:
                        break
                retained.reverse()
                current = retained
                current_len = sum(len(part) for part in current)
            else:
                current = []
                current_len = 0

        current.append(stripped)
        current_len += len(stripped)

    if current:
        yield "\n\n".join(current).strip()


def split_into_chunks(
    text: str,
    *,
    chunk_chars: int = 500,
    overlap_chars: int = 120,
) -> list[tuple[str | None, str]]:
    """Split *text* into ``(title, chunk_text)`` pairs suitable for indexing."""

    chunks: list[tuple[str | None, str]] = []
    for title, section_text in iter_sections(text):
        paragraphs = [part for part in section_text.split("\n\n") if part.strip()]
        for chunk_text in _chunk_paragraphs(
            paragraphs, chunk_chars=chunk_chars, overlap_chars=overlap_chars
        ):
            if chunk_text:
                chunks.append((title, chunk_text))

    if not chunks:
        normalized = text.strip()
        if normalized:
            paragraphs = [part for part in normalized.split("\n\n") if part.strip()]
            for chunk_text in _chunk_paragraphs(
                paragraphs, chunk_chars=chunk_chars, overlap_chars=overlap_chars
            ):
                if chunk_text:
                    chunks.append((None, chunk_text))

    return chunks


def list_markdown_files(directory: Path) -> Iterable[Path]:
    """Yield markdown post files sorted by name."""

    if not directory.exists():
        return []

    return sorted(
        (path for path in directory.glob("*.md") if path.is_file()),
        key=lambda item: item.stem,
    )
