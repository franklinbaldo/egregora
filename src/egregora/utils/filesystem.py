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

import frontmatter
import yaml

from egregora.utils.datetime_utils import parse_datetime_flexible
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

    try:
        # Validate that the matched pattern is a real date.
        return date.fromisoformat(match.group(1)).isoformat()
    except ValueError:
        # The pattern was not a valid date (e.g., "2023-99-99"), so fallback.
        return date_str


def format_frontmatter_datetime(raw_date: str | date | datetime) -> str:
    """Normalize a metadata date into the RSS-friendly ``YYYY-MM-DD HH:MM`` string."""
    try:
        dt = parse_datetime_flexible(raw_date, default_timezone=UTC)
        return dt.strftime("%Y-%m-%d %H:%M")
    except AttributeError:
        # This will be raised if parse_datetime_flexible returns None,
        # which covers all failure modes (None input, empty strings, bad data).
        return str(raw_date).strip() if raw_date is not None else ""


def _update_authors_file(authors_path: Path, author_ids: list[str]) -> int:
    """Load, update, and save the .authors.yml file.

    This is the core, shared logic for registering new authors.

    Args:
        authors_path: The path to the .authors.yml file.
        author_ids: A list of author IDs to ensure are registered.

    Returns:
        The number of new authors that were added to the file.

    """
    authors = _load_authors_yml(authors_path)
    new_ids = _register_new_authors(authors, author_ids)
    if new_ids:
        _save_authors_yml(authors_path, authors, len(new_ids))
    return len(new_ids)


def ensure_author_entries(output_dir: Path, author_ids: list[str] | None) -> None:
    """Ensure every referenced author has an entry in `.authors.yml`."""
    if not author_ids:
        return

    authors_path = _find_authors_yml(output_dir)
    _update_authors_file(authors_path, author_ids)


def _find_authors_yml(output_dir: Path) -> Path:
    """Finds the .authors.yml file by searching upwards for a `docs` directory."""
    current_dir = output_dir.resolve()
    # More robustly search up the tree for a 'docs' directory
    for parent in [current_dir, *current_dir.parents]:
        if parent.name == "docs":
            return parent / ".authors.yml"

    logger.warning(
        "Could not find 'docs' directory in ancestry of %s. "
        "Falling back to legacy path resolution for .authors.yml.",
        output_dir,
    )
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


def _resolve_filepath(output_dir: Path, date_prefix: str, base_slug: str) -> tuple[Path, str]:
    """Resolve a unique filepath and slug, handling collisions.

    Appends a numeric suffix to the slug if a file with the same name already exists.

    Args:
        output_dir: The directory where the file will be saved.
        date_prefix: The YYYY-MM-DD date prefix for the filename.
        base_slug: The initial slug to use.

    Returns:
        A tuple containing the unique Path object and the final resolved slug.

    """
    slug_candidate = base_slug
    filename = f"{date_prefix}-{slug_candidate}.md"
    filepath = safe_path_join(output_dir, filename)
    suffix = 2
    while filepath.exists():
        slug_candidate = f"{base_slug}-{suffix}"
        filename = f"{date_prefix}-{slug_candidate}.md"
        filepath = safe_path_join(output_dir, filename)
        suffix += 1
    return filepath, slug_candidate


def write_markdown_post(content: str, metadata: dict[str, Any], output_dir: Path) -> str:
    """Save a markdown post with YAML front matter and unique slugging."""
    required = ["title", "slug", "date"]
    for key in required:
        if key not in metadata:
            msg = f"Missing required metadata: {key}"
            raise ValueError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)

    date_prefix = _extract_clean_date(metadata["date"])
    base_slug = slugify(metadata["slug"])

    filepath, final_slug = _resolve_filepath(output_dir, date_prefix, base_slug)

    front_matter = _prepare_frontmatter(metadata, final_slug)

    if "authors" in front_matter:
        ensure_author_entries(output_dir, front_matter.get("authors"))

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    full_post = f"---\n{yaml_front}---\n\n{content}"
    filepath.write_text(full_post, encoding="utf-8")
    return str(filepath)


def _extract_authors_from_post(md_file: Path) -> set[str]:
    """Load a single post file and extract its author IDs."""
    try:
        post = frontmatter.load(str(md_file))
        authors_meta = post.metadata.get("authors")
        if not authors_meta:
            return set()

        # Normalize to a list
        if not isinstance(authors_meta, list):
            authors_meta = [authors_meta]

        return {str(a) for a in authors_meta if a}

    except OSError as exc:
        logger.debug("Skipping %s: %s", md_file, exc)
        return set()


def sync_authors_from_posts(posts_dir: Path, docs_dir: Path | None = None) -> int:
    """Scan all posts and ensure every referenced author exists in .authors.yml."""
    if docs_dir is None:
        docs_dir = posts_dir.resolve().parent.parent

    authors_path = docs_dir / ".authors.yml"

    all_author_ids: set[str] = set()
    for md_file in posts_dir.rglob("*.md"):
        all_author_ids.update(_extract_authors_from_post(md_file))

    if not all_author_ids:
        return 0

    new_count = _update_authors_file(authors_path, list(all_author_ids))
    if new_count > 0:
        logger.info("Synced %d new author(s) from posts to %s", new_count, authors_path)

    return new_count
