"""Author management utilities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import frontmatter
import yaml

from egregora.utils.exceptions import (
    AuthorExtractionError,
    AuthorsFileLoadError,
    AuthorsFileParseError,
    AuthorsFileSaveError,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def update_authors_file(authors_path: Path, author_ids: list[str]) -> int:
    """Load, update, and save the .authors.yml file.

    This is the core, shared logic for registering new authors.

    Args:
        authors_path: The path to the .authors.yml file.
        author_ids: A list of author IDs to ensure are registered.

    Returns:
        The number of new authors that were added to the file.

    """
    # Auto-create if missing
    if not authors_path.exists():
        authors = {}
        # Ensure directory exists
        authors_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        authors = load_authors_yml(authors_path)

    new_ids = register_new_authors(authors, author_ids)
    if new_ids:
        save_authors_yml(authors_path, authors, len(new_ids))
    return len(new_ids)


def ensure_author_entries(output_dir: Path, author_ids: list[str] | None) -> None:
    """Ensure every referenced author has an entry in `.authors.yml`."""
    if not author_ids:
        return

    authors_path = find_authors_yml(output_dir)
    update_authors_file(authors_path, author_ids)


def find_authors_yml(output_dir: Path) -> Path:
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


def load_authors_yml(path: Path) -> dict:
    """Loads the .authors.yml file."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as e:
        raise AuthorsFileLoadError(str(path), e) from e
    except yaml.YAMLError as e:
        raise AuthorsFileParseError(str(path), e) from e


def register_new_authors(authors: dict, author_ids: list[str]) -> list[str]:
    """Registers new authors."""
    new_ids = []
    for author_id in author_ids:
        if author_id and author_id not in authors:
            authors[author_id] = {
                "name": author_id,
                "url": f"profiles/{author_id}.md",
            }
            new_ids.append(author_id)
    return new_ids


def save_authors_yml(path: Path, authors: dict, count: int) -> None:
    """Saves the .authors.yml file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(authors, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Registered %d new author(s) in %s", count, path)
    except OSError as e:
        raise AuthorsFileSaveError(str(path), e) from e


def extract_authors_from_post(md_file: Path) -> set[str]:
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

    except OSError as e:
        raise AuthorExtractionError(str(md_file), e) from e


def sync_authors_from_posts(posts_dir: Path, docs_dir: Path | None = None) -> int:
    """Scan all posts and ensure every referenced author exists in .authors.yml."""
    authors_path = find_authors_yml(posts_dir)

    all_author_ids: set[str] = set()
    for md_file in posts_dir.rglob("*.md"):
        all_author_ids.update(extract_authors_from_post(md_file))

    if not all_author_ids:
        return 0

    new_count = update_authors_file(authors_path, list(all_author_ids))
    if new_count > 0:
        logger.info("Synced %d new author(s) from posts to %s", new_count, authors_path)

    return new_count
