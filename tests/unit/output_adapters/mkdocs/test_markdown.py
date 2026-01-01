"""Unit tests for MkDocs markdown writing utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from egregora.output_adapters.exceptions import MissingMetadataError
from egregora.output_adapters.mkdocs.markdown import write_markdown_post


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

    with patch("egregora.output_adapters.mkdocs.markdown.ensure_author_entries") as mock_ensure_author:
        result_path = write_markdown_post(content, metadata, output_dir)

    assert Path(result_path).exists()
    mock_ensure_author.assert_called_once()

    with open(result_path, encoding="utf-8") as f:
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
    with patch("egregora.output_adapters.mkdocs.markdown.ensure_author_entries"):
        first_path = write_markdown_post(content, metadata, output_dir)
    assert "collision-post.md" in first_path

    # Create a second post with the same slug and date
    with patch("egregora.output_adapters.mkdocs.markdown.ensure_author_entries"):
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
