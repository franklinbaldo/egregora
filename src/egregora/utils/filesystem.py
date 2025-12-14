"""Filesystem utilities for writing structured content.

This module consolidates file writing logic previously scattered across adapters.
It provides standard helpers for:
- Writing markdown posts with frontmatter
- Handling safe filenames and collision resolution
- Managing directory structures
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from egregora.utils.datetime_utils import parse_datetime_flexible

logger = logging.getLogger(__name__)

ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)
_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _extract_clean_date(date_obj: str | date | datetime) -> str:
    """Extract a clean ``YYYY-MM-DD`` date from user-provided input."""
    if isinstance(date_obj, datetime):
        return date_obj.date().isoformat()
    if isinstance(date_obj, date):
        return date_obj.isoformat()

    date_str = str(date_obj).strip()

    try:
        if len(date_str) == ISO_DATE_LENGTH and date_str[4] == "-" and date_str[7] == "-":
            date.fromisoformat(date_str)
            return date_str
    except ValueError:
        pass

    match = _DATE_PATTERN.search(date_str)
    if match:
        clean_date = match.group(1)
        try:
            date.fromisoformat(clean_date)
        except ValueError:
            pass
        else:
            return clean_date

    return date_str


def format_frontmatter_datetime(raw_date: str | date | datetime) -> str:
    """Normalize a metadata date into the RSS-friendly ``YYYY-MM-DD HH:MM`` string."""
    if raw_date is None:
        return ""

    dt = parse_datetime_flexible(raw_date, default_timezone=UTC)
    if dt is None:
        return str(raw_date).strip()

    return dt.strftime("%Y-%m-%d %H:%M")


def ensure_author_entries(output_dir: Path, author_ids: list[str] | None) -> None:
    """Ensure every referenced author has an entry in `.authors.yml`.

    This logic is specific to MkDocs/Material theme but stored here for reuse
    if other adapters adopt similar conventions.
    """
    if not author_ids:
        return

    authors_path = _find_authors_yml(output_dir)
    authors = _load_authors_yml(authors_path)

    new_ids = _register_new_authors(authors, author_ids)

    if new_ids:
        _save_authors_yml(authors_path, authors, len(new_ids))


def _find_authors_yml(output_dir: Path) -> Path:
    current = output_dir.resolve()
    for _ in range(5):  # Limit traversal depth
        if current.name == "docs" or (current / ".authors.yml").exists():
            return current / ".authors.yml"
        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    # Fallback: assume output_dir's grandparent is docs (posts/posts -> docs)
    return output_dir.resolve().parent.parent / ".authors.yml"


def _load_authors_yml(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _register_new_authors(authors: dict, author_ids: list[str]) -> list[str]:
    new_ids = []
    for author_id in author_ids:
        if author_id and author_id not in authors:
            authors[author_id] = {
                "name": author_id,
                "url": f"profiles/{author_id}.md",
            }
            new_ids.append(author_id)
    return new_ids


def _save_authors_yml(path: Path, authors: dict, count: int) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(authors, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Registered %d new author(s) in %s", count, path)
    except OSError as exc:
        logger.warning("Failed to update %s: %s", path, exc)


