"""Unit tests for filesystem utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from egregora.output_adapters.mkdocs.markdown_writer import (
    DirectoryCreationError,
    FileWriteError,
    MissingMetadataError,
    UniqueFilenameError,
    _resolve_filepath,
    _validate_post_metadata,
    _write_post_file,
    write_markdown_post,
)


# region: Tests for _validate_post_metadata
def test_validate_post_metadata_success():
    _validate_post_metadata({"title": "t", "slug": "s", "date": "d"})


def test_validate_post_metadata_raises_error_on_missing_keys():
    with pytest.raises(MissingMetadataError) as excinfo:
        _validate_post_metadata({"title": "t"})
    assert "slug" in str(excinfo.value)
    assert "date" in str(excinfo.value)


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
    for i in range(2, 5):  # max_attempts=3
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


def test_write_markdown_post_with_full_metadata(tmp_path: Path):
    """Verify that write_markdown_post handles a full set of metadata."""
    content = "This is the post content."
    metadata = {
        "title": "Full Metadata Test",
        "slug": "full-metadata-test",
        "date": "2023-10-27 10:00",
        "authors": ["Author One", "Author Two"],
        "tags": ["testing", "metadata"],
        "summary": "This is a test summary.",
        "category": "Technology",
    }
    output_dir = tmp_path

    with patch("egregora.output_adapters.mkdocs.markdown_writer.ensure_author_entries") as mock_ensure_authors:
        filepath_str = write_markdown_post(content, metadata, output_dir)
        filepath = Path(filepath_str)

        assert filepath.exists()
        mock_ensure_authors.assert_called_once_with(output_dir, ["Author One", "Author Two"])

        file_content = filepath.read_text()
        assert "title: Full Metadata Test" in file_content
        assert "slug: full-metadata-test" in file_content
        assert "date: 2023-10-27 10:00" in file_content
        assert "authors:" in file_content
        assert "- Author One" in file_content
        assert "- Author Two" in file_content
        assert "tags:" in file_content
        assert "- testing" in file_content
        assert "- metadata" in file_content
        assert "summary: This is a test summary." in file_content
        assert "category: Technology" in file_content
        assert content in file_content


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


# region: Coverage tests
def test_write_post_file_raises_file_write_error():
    """Verify that _write_post_file raises FileWriteError on OSError."""
    mock_path = MagicMock(spec=Path)
    mock_path.write_text.side_effect = OSError("Disk full")

    with pytest.raises(FileWriteError) as excinfo:
        _write_post_file(mock_path, "content", {"key": "value"})

    assert "Disk full" in str(excinfo.value)
    assert str(mock_path) in str(excinfo.value)


# endregion

@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for testing."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


def test_write_markdown_post_creates_file_with_correct_content_and_frontmatter(temp_output_dir: Path):
    """Test that write_markdown_post creates a file with the correct content and frontmatter."""
    content = "This is the post content."
    metadata = {
        "title": "Test Post",
        "slug": "test-post",
        "date": "2025-01-01",
        "authors": ["author1"],
        "tags": ["testing", "refactoring"],
    }

    filepath_str = write_markdown_post(content, metadata, temp_output_dir)
    filepath = Path(filepath_str)

    assert filepath.exists()

    with filepath.open(encoding="utf-8") as f:
        file_content = f.read()

    # Split the frontmatter and the content
    parts = file_content.split("---")
    frontmatter_str = parts[1]
    post_content = parts[2].strip()

    frontmatter = yaml.safe_load(frontmatter_str)

    expected_frontmatter = {
        "title": "Test Post",
        "slug": "test-post",
        "date": "2025-01-01 00:00",
        "authors": ["author1"],
        "tags": ["testing", "refactoring"],
    }

    assert frontmatter == expected_frontmatter
    assert post_content == content


def test_write_markdown_post_handles_filename_collision(temp_output_dir: Path):
    """Test that write_markdown_post correctly handles filename collisions."""
    content = "This is the second post."
    metadata = {"title": "Another Test Post", "slug": "test-post", "date": "2025-01-01"}

    # Create the first post
    write_markdown_post(
        "First post", {"title": "First", "slug": "test-post", "date": "2025-01-01"}, temp_output_dir
    )

    # Create the second post, which should have a different filename
    filepath_str = write_markdown_post(content, metadata, temp_output_dir)
    filepath = Path(filepath_str)

    assert filepath.name == "2025-01-01-test-post-2.md"

    with filepath.open(encoding="utf-8") as f:
        file_content = f.read()

    parts = file_content.split("---")
    frontmatter = yaml.safe_load(parts[1])

    assert frontmatter["slug"] == "test-post-2"


def test_write_markdown_post_raises_error_on_missing_metadata(temp_output_dir: Path):
    """Test that write_markdown_post raises MissingMetadataError if required metadata is missing."""
    content = "This content will not be written."
    metadata = {"title": "Test Post"}  # Missing slug and date

    with pytest.raises(MissingMetadataError) as excinfo:
        write_markdown_post(content, metadata, temp_output_dir)

    assert "slug" in str(excinfo.value)
    assert "date" in str(excinfo.value)


def test_write_markdown_post_unique_filename_error(temp_output_dir: Path):
    """Verify it raises UniqueFilenameError after too many collisions."""
    content = "Content."
    metadata = {"title": "Full Post", "slug": "full-post", "date": "2023-03-03"}
    output_dir = temp_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create files to cause collisions up to the limit (default 100 attempts)
    base_filepath = output_dir / "2023-03-03-full-post.md"
    base_filepath.touch()
    for i in range(2, 102):
        filepath = output_dir / f"2023-03-03-full-post-{i}.md"
        filepath.touch()

    with pytest.raises(UniqueFilenameError) as excinfo:
        write_markdown_post(content, metadata, output_dir)

    assert "full-post" in str(excinfo.value)
    assert "100" in str(excinfo.value)
