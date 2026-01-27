"""Markdown file writing utilities for the MkDocs adapter."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import yaml

from egregora.data_primitives.text import slugify
from egregora.knowledge.profiles import ensure_author_entries
from egregora.output_sinks.exceptions import (
    DirectoryCreationError,
    FileWriteError,
    MissingMetadataError,
    UniqueFilenameError,
)
from egregora.output_sinks.mkdocs.markdown_utils import (
    extract_clean_date,
    format_frontmatter_datetime,
)
from egregora.security.fs import safe_path_join

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def _prepare_frontmatter(metadata: dict[str, Any], slug: str) -> dict[str, Any]:
    """Prepare the YAML frontmatter dictionary from post metadata.

    Args:
        metadata: The raw metadata dictionary for the post.
        slug: The final, resolved slug for the post.

    Returns:
        A dictionary containing the formatted frontmatter.

    """
    front_matter = metadata.copy()
    front_matter["title"] = metadata["title"]
    front_matter["slug"] = slug
    front_matter["date"] = format_frontmatter_datetime(metadata["date"])
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
    for i in range(max_attempts + 1):
        # The first attempt (i=0) uses the base slug.
        # Subsequent attempts append a numeric suffix, starting from 2.
        slug_candidate = base_slug if i == 0 else f"{base_slug}-{i + 1}"
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
        raise MissingMetadataError(missing_keys)


def _write_post_file(filepath: Path, content: str, front_matter: dict[str, Any]) -> None:
    """Construct the full post content and write it to a file."""
    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    full_post = f"---\n{yaml_front}---\n\n{content}"
    try:
        filepath.write_text(full_post, encoding="utf-8")
    except OSError as e:
        raise FileWriteError(str(filepath), e) from e


def write_markdown_post(content: str, metadata: dict[str, Any], output_dir: Path) -> str:
    """Save a markdown post with YAML front matter and unique slugging."""
    _validate_post_metadata(metadata)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise DirectoryCreationError(str(output_dir), e) from e

    date_prefix = extract_clean_date(metadata["date"])
    base_slug = slugify(metadata["slug"])

    filepath, final_slug = _resolve_filepath(output_dir, date_prefix, base_slug)

    front_matter = _prepare_frontmatter(metadata, final_slug)

    if "authors" in front_matter:
        ensure_author_entries(output_dir, front_matter.get("authors"))

    _write_post_file(filepath, content, front_matter)

    return str(filepath)
