from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from egregora.output_adapters.exceptions import (
    DateExtractionError,
    FrontmatterDateFormattingError,
    MissingMetadataError,
    UniqueFilenameError,
)
from egregora.output_adapters.mkdocs.adapter import (
    _extract_clean_date,
    _resolve_filepath,
    _validate_post_metadata,
    format_frontmatter_datetime,
    write_markdown_post,
)


@pytest.fixture
def sample_metadata():
    return {
        "title": "Test Post",
        "slug": "test-post",
        "date": "2024-01-01",
        "tags": ["testing", "refactoring"],
        "authors": ["test-author"],
        "summary": "This is a test post.",
    }


def test_write_markdown_post_success(tmp_path: Path, sample_metadata: dict):
    """Verify a markdown post is written correctly with valid inputs."""
    content = "This is the post content."
    filepath_str = write_markdown_post(content, sample_metadata, tmp_path)
    filepath = Path(filepath_str)

    assert filepath.exists()
    assert filepath.name == "2024-01-01-test-post.md"

    # Verify content and frontmatter
    full_content = filepath.read_text(encoding="utf-8")
    assert content in full_content

    frontmatter_str = full_content.split("---")[1]
    frontmatter = yaml.safe_load(frontmatter_str)

    assert frontmatter["title"] == sample_metadata["title"]
    assert frontmatter["slug"] == sample_metadata["slug"]
    assert frontmatter["date"] == "2024-01-01 00:00"


def test_resolve_filepath_collision(tmp_path: Path):
    """Test that filename collisions are resolved with a numeric suffix."""
    base_slug = "collision-post"
    date_prefix = "2024-01-01"

    # Create the first file
    (tmp_path / f"{date_prefix}-{base_slug}.md").touch()

    # Resolve the path, expecting a new slug
    filepath, final_slug = _resolve_filepath(tmp_path, date_prefix, base_slug)

    assert final_slug == f"{base_slug}-2"
    assert filepath.name == f"{date_prefix}-{base_slug}-2.md"


def test_resolve_filepath_no_collision(tmp_path: Path):
    """Test that the original slug is used when there's no collision."""
    base_slug = "no-collision"
    date_prefix = "2024-01-01"

    filepath, final_slug = _resolve_filepath(tmp_path, date_prefix, base_slug)

    assert final_slug == base_slug
    assert filepath.name == f"{date_prefix}-{base_slug}.md"


def test_resolve_filepath_max_attempts_exceeded(tmp_path: Path):
    """Test that an error is raised after too many filename collisions."""
    base_slug = "full-collision"
    date_prefix = "2024-01-01"

    # Create files to exhaust all attempts
    (tmp_path / f"{date_prefix}-{base_slug}.md").touch()
    for i in range(2, 103):
        (tmp_path / f"{date_prefix}-{base_slug}-{i}.md").touch()

    with pytest.raises(UniqueFilenameError):
        _resolve_filepath(tmp_path, date_prefix, base_slug, max_attempts=100)


def test_validate_post_metadata_missing_keys():
    """Test that metadata validation fails with missing required keys."""
    with pytest.raises(MissingMetadataError) as excinfo:
        _validate_post_metadata({"title": "Incomplete Post"})
    assert "slug" in str(excinfo.value)
    assert "date" in str(excinfo.value)


def test_extract_clean_date():
    """Test various date formats are correctly extracted to YYYY-MM-DD."""
    assert _extract_clean_date("2024-03-15") == "2024-03-15"
    assert _extract_clean_date(date(2024, 3, 15)) == "2024-03-15"
    assert _extract_clean_date("A post from 2024-03-15 about something.") == "2024-03-15"

    with pytest.raises(DateExtractionError):
        _extract_clean_date("no date here")


def test_format_frontmatter_datetime():
    """Test date formatting for YAML frontmatter."""
    assert format_frontmatter_datetime("2024-01-01") == "2024-01-01 00:00"

    with pytest.raises(FrontmatterDateFormattingError):
        format_frontmatter_datetime("not a date")
