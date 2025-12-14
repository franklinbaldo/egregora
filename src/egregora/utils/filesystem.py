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
from egregora.utils.frontmatter_utils import read_frontmatter_only
from egregora.utils.paths import safe_path_join, slugify

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


def sync_authors_from_posts(posts_dir: Path, docs_dir: Path | None = None) -> int:
    """Scan all posts and ensure every referenced author exists in .authors.yml.

    This function traverses all markdown files in posts_dir, extracts author IDs
    from their frontmatter, and registers any missing authors in .authors.yml.

    Args:
        posts_dir: Directory containing post markdown files (recursively scanned).
        docs_dir: Root docs directory where .authors.yml lives. If None, derived from posts_dir.

    Returns:
        Number of new authors registered.

    """
    if docs_dir is None:
        # Derive docs_dir: posts_dir is typically docs/posts/posts, so go up 2 levels
        docs_dir = posts_dir.resolve().parent.parent

    authors_path = docs_dir / ".authors.yml"
    authors = _load_authors_yml(authors_path)

    # Collect all unique author IDs from posts
    all_author_ids: set[str] = set()

    for md_file in posts_dir.rglob("*.md"):
        try:
            frontmatter = read_frontmatter_only(md_file)
            if frontmatter and "authors" in frontmatter:
                author_list = frontmatter["authors"]
                if isinstance(author_list, list):
                    all_author_ids.update(str(a) for a in author_list if a)
                elif author_list:
                    all_author_ids.add(str(author_list))
        except OSError as exc:
            logger.debug("Skipping %s: %s", md_file, exc)
            continue

    # Register missing authors
    new_ids = _register_new_authors(authors, list(all_author_ids))

    if new_ids:
        _save_authors_yml(authors_path, authors, len(new_ids))
        logger.info("Synced %d new author(s) from posts to %s", len(new_ids), authors_path)

    return len(new_ids)
