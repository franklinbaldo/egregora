"""Filesystem utilities for writing structured content.

This module consolidates file writing logic previously scattered across adapters.
It provides standard helpers for:
- Writing markdown posts with frontmatter
- Handling safe filenames and collision resolution
- Managing directory structures
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import yaml

from egregora.utils import safe_path_join, slugify
from egregora.utils.authors import ensure_author_entries
from egregora.utils.datetime_utils import (
    extract_clean_date,
    format_frontmatter_datetime,
)

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


class FilesystemError(Exception):
    """Base exception for filesystem-related errors."""


class MissingMetadataError(FilesystemError):
    """Raised when required metadata for a post is missing."""

    def __init__(self, missing_keys: list[str]) -> None:
        self.missing_keys = missing_keys
        message = f"Missing required metadata keys: {', '.join(missing_keys)}"
        super().__init__(message)


class UniqueFilenameError(FilesystemError):
    """Raised when a unique filename cannot be generated after a set number of attempts."""

    def __init__(self, base_slug: str, attempts: int) -> None:
        self.base_slug = base_slug
        self.attempts = attempts
        message = f"Could not generate a unique filename for slug '{base_slug}' after {attempts} attempts."
        super().__init__(message)


class FilesystemOperationError(FilesystemError):
    """Base exception for file I/O errors."""

    def __init__(self, path: str, original_exception: Exception, message: str | None = None) -> None:
        self.path = path
        self.original_exception = original_exception
        if message is None:
            message = f"An error occurred at path: {self.path}. Original error: {original_exception}"
        super().__init__(message)


class DirectoryCreationError(FilesystemOperationError):
    """Raised when creating a directory fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to create directory at: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class FileWriteError(FilesystemOperationError):
    """Raised when writing a file fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to write file to: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)
