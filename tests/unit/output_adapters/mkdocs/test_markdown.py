"""Unit tests for MkDocs markdown writing utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from egregora.output_sinks.exceptions import MissingMetadataError, UniqueFilenameError
from egregora.output_sinks.mkdocs.markdown import _resolve_filepath, write_markdown_post


def test_write_markdown_post_creates_file_with_frontmatter(tmp_path: Path):
    """Verify that a markdown post is written with correct frontmatter and content."""
    output_dir = tmp_path / "posts"
    metadata = {
        "title": "Test Post",
        "slug": "test-post",
        "date": "2025-01-15",
        "tags": ["testing", "refactoring"],
        "summary": "This is a test post.",
        "authors": ["test-author"],
    }
    content = "This is the content of the test post."

    with patch("egregora.output_sinks.mkdocs.markdown.ensure_author_entries") as mock_ensure_author:
        result_path = write_markdown_post(content, metadata, output_dir)

    assert Path(result_path).exists()
    mock_ensure_author.assert_called_once()

    with Path(result_path).open(encoding="utf-8") as f:
        file_content = f.read()

    # Verify frontmatter and content are correctly written
    _, frontmatter_str, post_content = file_content.split("---", 2)
    frontmatter = yaml.safe_load(frontmatter_str)

    assert frontmatter["title"] == "Test Post"
    assert frontmatter["slug"] == "test-post"
    assert "2025-01-15" in str(frontmatter["date"])
    assert frontmatter["tags"] == ["testing", "refactoring"]
    assert frontmatter["summary"] == "This is a test post."
    assert frontmatter["authors"] == ["test-author"]
    assert post_content.strip() == content


def test_write_markdown_post_handles_filename_collisions(tmp_path: Path):
    """Verify that filename collisions are handled by appending a numeric suffix."""
    output_dir = tmp_path / "posts"
    metadata = {"title": "Collision Post", "slug": "collision-post", "date": "2025-01-16"}
    content = "This is a post that will have a filename collision."

    # Create the first post
    with patch("egregora.output_sinks.mkdocs.markdown.ensure_author_entries"):
        first_path = write_markdown_post(content, metadata, output_dir)
    assert "collision-post.md" in first_path

    # Create a second post with the same slug and date
    with patch("egregora.output_sinks.mkdocs.markdown.ensure_author_entries"):
        second_path = write_markdown_post(content, metadata, output_dir)
    assert "collision-post-2.md" in second_path

    # Verify that both files exist
    assert Path(first_path).exists()
    assert Path(second_path).exists()


def test_write_markdown_post_raises_error_for_missing_metadata(tmp_path: Path):
    """Verify that a `MissingMetadataError` is raised if required metadata is missing."""
    output_dir = tmp_path / "posts"
    metadata = {"title": "Missing Slug and Date"}  # Missing "slug" and "date"
    content = "This post is missing required metadata."

    with pytest.raises(MissingMetadataError) as excinfo:
        write_markdown_post(content, metadata, output_dir)

    assert "slug" in str(excinfo.value)
    assert "date" in str(excinfo.value)


def test_resolve_filepath_no_collision(tmp_path: Path):
    """
    Tests that _resolve_filepath returns the original path and slug when no file collision occurs.
    """
    output_dir = tmp_path
    date_prefix = "2023-01-01"
    base_slug = "my-first-post"

    filepath, slug = _resolve_filepath(output_dir, date_prefix, base_slug)

    expected_filename = "2023-01-01-my-first-post.md"
    assert filepath == output_dir / expected_filename
    assert slug == base_slug


def test_resolve_filepath_single_collision(tmp_path: Path):
    """
    Tests that _resolve_filepath appends a numeric suffix to the slug on a single file collision.
    """
    output_dir = tmp_path
    date_prefix = "2023-01-01"
    base_slug = "my-post"

    # Create the original file to cause a collision
    (output_dir / "2023-01-01-my-post.md").touch()

    filepath, slug = _resolve_filepath(output_dir, date_prefix, base_slug)

    expected_filename = "2023-01-01-my-post-2.md"
    assert filepath == output_dir / expected_filename
    assert slug == "my-post-2"


def test_resolve_filepath_multiple_collisions(tmp_path: Path):
    """
    Tests that _resolve_filepath finds the next available numeric suffix with multiple file collisions.
    """
    output_dir = tmp_path
    date_prefix = "2023-01-01"
    base_slug = "another-post"

    # Create multiple files to cause collisions
    (output_dir / "2023-01-01-another-post.md").touch()
    (output_dir / "2023-01-01-another-post-2.md").touch()
    (output_dir / "2023-01-01-another-post-3.md").touch()

    filepath, slug = _resolve_filepath(output_dir, date_prefix, base_slug)

    expected_filename = "2023-01-01-another-post-4.md"
    assert filepath == output_dir / expected_filename
    assert slug == "another-post-4"


def test_resolve_filepath_raises_error_on_max_attempts(tmp_path: Path):
    """
    Tests that _resolve_filepath raises UniqueFilenameError when it cannot find a unique name.
    """
    output_dir = tmp_path
    date_prefix = "2023-01-01"
    base_slug = "full-post"
    max_attempts = 3

    # Create files to exhaust all attempts
    (output_dir / "2023-01-01-full-post.md").touch()
    (output_dir / "2023-01-01-full-post-2.md").touch()
    (output_dir / "2023-01-01-full-post-3.md").touch()
    (output_dir / "2023-01-01-full-post-4.md").touch()

    with pytest.raises(UniqueFilenameError):
        _resolve_filepath(output_dir, date_prefix, base_slug, max_attempts=max_attempts)
