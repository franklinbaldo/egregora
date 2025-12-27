"""Unit tests for filesystem utilities."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import date, datetime

from egregora.utils.exceptions import (
    DirectoryCreationError,
    FileWriteError,
    DateExtractionError,
    MissingMetadataError,
    UniqueFilenameError,
    FrontmatterDateFormattingError,
)
from egregora.utils.filesystem import (
    _extract_clean_date,
    _validate_post_metadata,
    format_frontmatter_datetime,
    _resolve_filepath,
    write_markdown_post,
)

# region: Tests for _extract_clean_date
def test_extract_clean_date_with_datetime():
    assert _extract_clean_date(datetime(2023, 1, 1, 12, 30)) == "2023-01-01"

def test_extract_clean_date_with_date():
    assert _extract_clean_date(date(2023, 1, 1)) == "2023-01-01"

def test_extract_clean_date_with_string():
    assert _extract_clean_date("2023-01-01") == "2023-01-01"

def test_extract_clean_date_with_string_and_time():
    assert _extract_clean_date("2023-01-01 12:30") == "2023-01-01"

def test_extract_clean_date_raises_on_no_date_in_string():
    with pytest.raises(DateExtractionError):
        _extract_clean_date("hello world")

def test_extract_clean_date_raises_error_on_invalid_date():
    """Verify that _extract_clean_date raises DateExtractionError for invalid dates."""
    invalid_date_str = "2023-99-99"
    with pytest.raises(DateExtractionError) as excinfo:
        _extract_clean_date(invalid_date_str)

    assert "Could not extract a valid date" in str(excinfo.value)
    assert invalid_date_str in str(excinfo.value)

# endregion

# region: Tests for _validate_post_metadata
def test_validate_post_metadata_success():
    _validate_post_metadata({"title": "t", "slug": "s", "date": "d"})

def test_validate_post_metadata_raises_error_on_missing_keys():
    with pytest.raises(MissingMetadataError) as excinfo:
        _validate_post_metadata({"title": "t"})
    assert "slug" in str(excinfo.value)
    assert "date" in str(excinfo.value)

def test_format_frontmatter_datetime_raises_on_invalid_date():
    with pytest.raises(FrontmatterDateFormattingError):
        format_frontmatter_datetime("invalid-date")

# endregion

# region: Tests for _resolve_filepath
def test_resolve_filepath_no_collision(tmp_path: Path):
    output_dir = tmp_path
    filepath, slug = _resolve_filepath(output_dir, "2023-01-01", "test-slug")
    assert slug == "test-slug"
    assert filepath == output_dir / "2023-01-01-test-slug.md"

def test_resolve_filepath_with_collision(tmp_path: Path):
    output_dir = tmp_path
    (output_dir / "2023-01-01-test-slug.md").touch()
    filepath, slug = _resolve_filepath(output_dir, "2023-01-01", "test-slug")
    assert slug == "test-slug-2"
    assert filepath == output_dir / "2023-01-01-test-slug-2.md"

def test_resolve_filepath_raises_error_after_max_attempts(tmp_path: Path):
    output_dir = tmp_path
    (output_dir / "2023-01-01-test-slug.md").touch()
    # Create files to exhaust attempts
    for i in range(2, 5): # max_attempts=3
        (output_dir / f"2023-01-01-test-slug-{i}.md").touch()

    with pytest.raises(UniqueFilenameError):
        _resolve_filepath(output_dir, "2023-01-01", "test-slug", max_attempts=3)

# endregion

# region: Tests for write_markdown_post (including exception handling)
def test_write_markdown_post_success(tmp_path: Path):
    content = "Hello"
    metadata = {"title": "Test", "slug": "test", "date": "2023-01-01"}
    output_dir = tmp_path

    filepath_str = write_markdown_post(content, metadata, output_dir)
    filepath = Path(filepath_str)

    assert filepath.exists()
    file_content = filepath.read_text()
    assert "title: Test" in file_content
    assert "slug: test" in file_content
    assert "date: 2023-01-01 00:00" in file_content
    assert "---" in file_content
    assert "Hello" in file_content

def test_write_markdown_post_raises_directory_creation_error(tmp_path: Path, monkeypatch):
    """Verify that write_markdown_post raises DirectoryCreationError on mkdir failure."""
    mock_mkdir = MagicMock(side_effect=OSError("Permission denied"))
    monkeypatch.setattr(Path, "mkdir", mock_mkdir)
    metadata = {"title": "t", "slug": "s", "date": "2023-01-01"}
    with pytest.raises(DirectoryCreationError):
        write_markdown_post("c", metadata, tmp_path)

def test_write_markdown_post_raises_file_write_error(tmp_path: Path, monkeypatch):
    """Verify that write_markdown_post raises FileWriteError on write_text failure."""
    mock_write_text = MagicMock(side_effect=OSError("Disk full"))
    monkeypatch.setattr(Path, "write_text", mock_write_text)
    metadata = {"title": "t", "slug": "s", "date": "2023-01-01"}
    with pytest.raises(FileWriteError):
        write_markdown_post("c", metadata, tmp_path)

# endregion
