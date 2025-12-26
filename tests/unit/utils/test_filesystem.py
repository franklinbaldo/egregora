"""Unit tests for filesystem utilities."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest

from egregora.utils.exceptions import (
    FrontmatterDateFormattingError,
    MissingMetadataError,
    UniqueFilenameError,
)
from egregora.utils.filesystem import (
    _extract_clean_date,
    format_frontmatter_datetime,
    write_markdown_post,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("input_date", "expected"),
    [
        ("2023-10-26", "2023-10-26"),
        (date(2023, 10, 26), "2023-10-26"),
        (datetime(2023, 10, 26, 10, 30), "2023-10-26"),
        ("  2023-10-26T10:30:00Z  ", "2023-10-26"),
        ("Some random string 2023-10-26", "2023-10-26"),
        ("No date here", "No date here"),
        ("2023-99-99", "2023-99-99"),  # Invalid date pattern
        ("", ""),
    ],
)
def test_extract_clean_date(input_date, expected):
    """
    GIVEN: Various date-like inputs (string, date, datetime).
    WHEN: The _extract_clean_date function is called.
    THEN: It should return a clean YYYY-MM-DD string or the original string if no date is found.
    """
    assert _extract_clean_date(input_date) == expected


def test_write_markdown_post_missing_metadata_raises_error(tmp_path: Path):
    """
    GIVEN: A call to write_markdown_post with missing metadata (missing slug and date).
    WHEN: The function is executed.
    THEN: It should raise MissingMetadataError.
    """
    output_dir = tmp_path
    content = "This is a test post."
    metadata = {"title": "Test Title"}  # Missing "slug" and "date"

    with pytest.raises(MissingMetadataError) as exc_info:
        write_markdown_post(content, metadata, output_dir)

    assert "slug" in exc_info.value.missing_keys
    assert "date" in exc_info.value.missing_keys
    assert "title" not in exc_info.value.missing_keys


def test_write_markdown_post_handles_filename_collision(tmp_path: Path):
    """
    GIVEN: An output directory already containing posts with similar names.
    WHEN: A new post is written with a slug that would collide.
    THEN: The function should append a numeric suffix to create a unique filename.
    """
    output_dir = tmp_path
    content = "This is a test post."
    metadata = {
        "title": "My Post",
        "slug": "my-post",
        "date": "2023-01-01",
    }

    # Create existing files to cause a collision
    (output_dir / "2023-01-01-my-post.md").touch()
    (output_dir / "2023-01-01-my-post-2.md").touch()

    # The new file should be named with the next available suffix, which is "-3"
    expected_path = output_dir / "2023-01-01-my-post-3.md"

    result_path = write_markdown_post(content, metadata, output_dir)

    assert result_path == str(expected_path)
    assert expected_path.exists()


def test_write_markdown_post_raises_error_after_too_many_collisions(tmp_path: Path):
    """
    GIVEN: A directory where 101 colliding filenames already exist.
    WHEN: write_markdown_post is called, triggering the filename resolution.
    THEN: It should raise UniqueFilenameError after exhausting all attempts.
    """
    output_dir = tmp_path
    metadata = {
        "title": "My Post",
        "slug": "my-post",
        "date": "2023-01-01",
    }

    # Create 101 files to exhaust the default attempts (100 suffixes + original)
    (output_dir / "2023-01-01-my-post.md").touch()
    for i in range(2, 103):
        (output_dir / f"2023-01-01-my-post-{i}.md").touch()

    with pytest.raises(UniqueFilenameError) as exc_info:
        write_markdown_post("content", metadata, output_dir)

    assert exc_info.value.base_slug == "my-post"
    assert exc_info.value.attempts == 100


def test_format_frontmatter_datetime_raises_on_invalid_date():
    """Test that format_frontmatter_datetime raises on unparseable date."""
    with pytest.raises(FrontmatterDateFormattingError) as excinfo:
        format_frontmatter_datetime("not-a-real-date")
    assert excinfo.value.date_str == "not-a-real-date"
