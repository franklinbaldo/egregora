"""Tests for filesystem utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from egregora.utils.exceptions import (
    FrontmatterDateFormattingError,
    MissingMetadataError,
)
from egregora.utils.filesystem import write_markdown_post

BASE_METADATA = {
    "title": "Test Title",
    "slug": "test-slug",
    "date": "2023-01-01",
}


def test_write_markdown_post_missing_title_raises_error(tmp_path: Path):
    """Verify it raises MissingMetadataError if 'title' is missing."""
    metadata = BASE_METADATA.copy()
    del metadata["title"]
    with pytest.raises(MissingMetadataError, match="title"):
        write_markdown_post("content", metadata, tmp_path)


def test_write_markdown_post_missing_slug_raises_error(tmp_path: Path):
    """Verify it raises MissingMetadataError if 'slug' is missing."""
    metadata = BASE_METADATA.copy()
    del metadata["slug"]
    with pytest.raises(MissingMetadataError, match="slug"):
        write_markdown_post("content", metadata, tmp_path)


def test_write_markdown_post_missing_date_raises_error(tmp_path: Path):
    """Verify it raises MissingMetadataError if 'date' is missing."""
    metadata = BASE_METADATA.copy()
    del metadata["date"]
    with pytest.raises(MissingMetadataError, match="date"):
        write_markdown_post("content", metadata, tmp_path)


def test_write_markdown_post_invalid_date_raises_error(tmp_path: Path):
    """Verify it raises FrontmatterDateFormattingError for a bad date."""
    metadata = BASE_METADATA.copy()
    metadata["date"] = "not-a-real-date"
    with pytest.raises(FrontmatterDateFormattingError):
        write_markdown_post("content", metadata, tmp_path)


def test_write_markdown_post_success(tmp_path: Path):
    """Verify it writes a valid markdown file on success."""
    content = "This is the post content."
    metadata = {
        "title": "My Test Post",
        "slug": "my-test-post",
        "date": "2023-11-20",
        "tags": ["testing", "python"],
    }

    filepath_str = write_markdown_post(content, metadata, tmp_path)
    filepath = Path(filepath_str)

    assert filepath.exists()
    assert filepath.name == "2023-11-20-my-test-post.md"

    # Verify content
    from frontmatter import load

    post = load(filepath)
    assert post.content.strip() == content
    assert post["title"] == "My Test Post"
    assert post["slug"] == "my-test-post"
    assert post["date"] == "2023-11-20 00:00"
    assert post["tags"] == ["testing", "python"]
