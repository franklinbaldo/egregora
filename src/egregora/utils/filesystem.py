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
from typing import Any

import yaml

from egregora.utils.datetime_utils import parse_datetime_flexible
from egregora.utils.paths import safe_path_join, slugify

logger = logging.getLogger(__name__)

ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)
_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _extract_clean_date(date_str: str) -> str:
    """Extract a clean ``YYYY-MM-DD`` date from user-provided strings."""
    import datetime

    date_str = date_str.strip()

    try:
        if len(date_str) == ISO_DATE_LENGTH and date_str[4] == "-" and date_str[7] == "-":
            datetime.date.fromisoformat(date_str)
            return date_str
    except (ValueError, AttributeError):
        pass

    match = _DATE_PATTERN.match(date_str)
    if match:
        clean_date = match.group(1)
        try:
            datetime.date.fromisoformat(clean_date)
        except (ValueError, AttributeError):
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

    # Navigate up from output_dir to find docs directory
    # output_dir might be: docs/posts/posts/ (for posts with blog plugin structure)
    # We need to find docs/.authors.yml
    current = output_dir.resolve()
    docs_dir = None
    for _ in range(5):  # Limit traversal depth
        if current.name == "docs" or (current / ".authors.yml").exists():
            docs_dir = current
            break
        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent
    
    if docs_dir is None:
        # Fallback: assume output_dir's grandparent is docs (posts/posts -> docs)
        docs_dir = output_dir.resolve().parent.parent
    
    authors_path = docs_dir / ".authors.yml"

    try:
        authors = yaml.safe_load(authors_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        authors = {}

    new_ids: list[str] = []
    for author_id in author_ids:
        if not author_id:
            continue
        if author_id in authors:
            continue
        authors[author_id] = {"name": author_id}
        new_ids.append(author_id)

    if not new_ids:
        return

    try:
        authors_path.parent.mkdir(parents=True, exist_ok=True)
        authors_path.write_text(
            yaml.dump(authors, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Registered %d new author(s) in %s", len(new_ids), authors_path)
    except OSError as exc:
        logger.warning("Failed to update %s: %s", authors_path, exc)


def write_markdown_post(content: str, metadata: dict[str, Any], output_dir: Path) -> str:
    """Save a markdown post with YAML front matter and unique slugging.

    Handles:
    - Slug generation and collision resolution
    - Date formatting
    - Frontmatter serialization
    - Author registration (side effect)
    """
    required = ["title", "slug", "date"]
    for key in required:
        if key not in metadata:
            msg = f"Missing required metadata: {key}"
            raise ValueError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)

    raw_date = metadata["date"]
    date_prefix = _extract_clean_date(raw_date)

    base_slug = slugify(metadata["slug"])
    slug_candidate = base_slug
    filename = f"{date_prefix}-{slug_candidate}.md"
    filepath = safe_path_join(output_dir, filename)
    suffix = 2
    while filepath.exists():
        slug_candidate = f"{base_slug}-{suffix}"
        filename = f"{date_prefix}-{slug_candidate}.md"
        filepath = safe_path_join(output_dir, filename)
        suffix += 1

    front_matter = {
        "title": metadata["title"],
        "slug": slug_candidate,
    }

    front_matter["date"] = format_frontmatter_datetime(raw_date)

    if "authors" in metadata:
        ensure_author_entries(output_dir, metadata.get("authors"))

    if "tags" in metadata:
        front_matter["tags"] = metadata["tags"]
    if "summary" in metadata:
        front_matter["summary"] = metadata["summary"]
    if "authors" in metadata:
        front_matter["authors"] = metadata["authors"]
    if "category" in metadata:
        front_matter["category"] = metadata["category"]

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    full_post = f"---\n{yaml_front}---\n\n{content}"
    filepath.write_text(full_post, encoding="utf-8")
    return str(filepath)
