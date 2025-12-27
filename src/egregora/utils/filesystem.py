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
from typing import TYPE_CHECKING, Any

import yaml

from egregora.utils.authors import ensure_author_entries
from egregora.utils.datetime_utils import parse_datetime_flexible
from egregora.utils.exceptions import (
    FrontmatterDateFormattingError,
    MissingPostMetadataError,
    UniqueFilenameError,
)
from egregora.utils.paths import safe_path_join, slugify

if TYPE_CHECKING:
    from pathlib import Path

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

    match = _DATE_PATTERN.search(date_str)
    if not match:
        return date_str  # No date pattern found.

    # Use our robust parser on the *matched part* of the string.
    parsed_dt = parse_datetime_flexible(match.group(1))
    if parsed_dt:
        return parsed_dt.date().isoformat()

    # The pattern was not a valid date (e.g., "2023-99-99"), so fallback.
    return date_str


def format_frontmatter_datetime(raw_date: str | date | datetime) -> str:
    """Normalize a metadata date into the RSS-friendly ``YYYY-MM-DD HH:MM`` string."""
    try:
        dt = parse_datetime_flexible(raw_date, default_timezone=UTC)
        if dt is None:
            raise AttributeError("Parsed datetime is None")
        return dt.strftime("%Y-%m-%d %H:%M")
    except (AttributeError, ValueError) as e:
        # This will be raised if parse_datetime_flexible returns None,
        # which covers all failure modes (None input, empty strings, bad data).
        raise FrontmatterDateFormattingError(str(raw_date), e) from e


def _prepare_frontmatter(metadata: dict[str, Any], slug: str) -> dict[str, Any]:
    """Prepare the YAML frontmatter dictionary from post metadata.

    Args:
        metadata: The raw metadata dictionary for the post.
        slug: The final, resolved slug for the post.

    Returns:
        A dictionary containing the formatted frontmatter.

    """
    front_matter = {
        "title": metadata["title"],
        "slug": slug,
        "date": format_frontmatter_datetime(metadata["date"]),
    }
    for key in ["tags", "summary", "authors", "category"]:
        if key in metadata:
            front_matter[key] = metadata[key]
    return front_matter


def _resolve_filepath(
    output_dir: Path, date_prefix: str, base_slug: str, max_attempts: int = 100
) -> tuple[Path, str]:
    """Resolve a unique filepath and slug, handling collisions.

    Appends a numeric suffix to the slug if a file with the same name already exists.

    Args:
        output_dir: The directory where the file will be saved.
        date_prefix: The YYYY-MM-DD date prefix for the filename.
        base_slug: The initial slug to use.
        max_attempts: The maximum number of attempts to find a unique filename.

    Returns:
        A tuple containing the unique Path object and the final resolved slug.

    Raises:
        UniqueFilenameError: If a unique filename cannot be found after max_attempts.

    """
    original_filename = f"{date_prefix}-{base_slug}.md"
    original_filepath = safe_path_join(output_dir, original_filename)

    if not original_filepath.exists():
        return original_filepath, base_slug

    for i in range(2, max_attempts + 2):
        slug_candidate = f"{base_slug}-{i}"
        filename = f"{date_prefix}-{slug_candidate}.md"
        filepath = safe_path_join(output_dir, filename)
        if not filepath.exists():
            return filepath, slug_candidate

    raise UniqueFilenameError(base_slug, max_attempts)


def _validate_post_metadata(metadata: dict[str, Any]) -> None:
    """Ensure required metadata keys are present."""
    required = {"title", "slug", "date"}
    missing_keys = list(required - set(metadata.keys()))
    if missing_keys:
        raise MissingPostMetadataError(missing_keys)


def _write_post_file(filepath: Path, content: str, front_matter: dict[str, Any]) -> None:
    """Construct the full post content and write it to a file."""
    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    full_post = f"---\n{yaml_front}---\n\n{content}"
    filepath.write_text(full_post, encoding="utf-8")


def write_markdown_post(content: str, metadata: dict[str, Any], output_dir: Path) -> str:
    """Save a markdown post with YAML front matter and unique slugging."""
    _validate_post_metadata(metadata)

    output_dir.mkdir(parents=True, exist_ok=True)

    date_prefix = _extract_clean_date(metadata["date"])
    base_slug = slugify(metadata["slug"])

    filepath, final_slug = _resolve_filepath(output_dir, date_prefix, base_slug)

    front_matter = _prepare_frontmatter(metadata, final_slug)

    if "authors" in front_matter:
        ensure_author_entries(output_dir, front_matter.get("authors"))

    _write_post_file(filepath, content, front_matter)

    return str(filepath)
