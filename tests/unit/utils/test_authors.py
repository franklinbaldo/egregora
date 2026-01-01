"""Unit tests for author management utilities."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from egregora.utils.authors import (
    AuthorExtractionError,
    AuthorsFileLoadError,
    AuthorsFileParseError,
    AuthorsFileSaveError,
    ensure_author_entries,
    extract_authors_from_post,
    load_authors_yml,
    save_authors_yml,
    sync_authors_from_posts,
)

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture


def test_load_authors_yml_raises_on_os_error():
    """Should raise AuthorsFileLoadError if the file cannot be read."""
    mock_path = MagicMock(spec=Path)
    mock_path.read_text.side_effect = OSError("File not found")

    with pytest.raises(AuthorsFileLoadError):
        load_authors_yml(mock_path)


def test_load_authors_yml_raises_on_yaml_error():
    """Should raise AuthorsFileParseError if the YAML is malformed."""
    mock_path = MagicMock(spec=Path)
    mock_path.read_text.return_value = "invalid: yaml:"

    with pytest.raises(AuthorsFileParseError):
        load_authors_yml(mock_path)


def test_save_authors_yml_raises_on_os_error():
    """Should raise AuthorsFileSaveError if the file cannot be written."""
    mock_path = MagicMock(spec=Path)
    mock_path.write_text.side_effect = OSError("Permission denied")

    with pytest.raises(AuthorsFileSaveError):
        save_authors_yml(mock_path, {"author1": {}}, 1)


def test_extract_authors_from_post_raises_on_os_error():
    """Should raise AuthorExtractionError if the post file cannot be read."""
    mock_file = MagicMock(spec=Path)
    mock_file.read_text.side_effect = OSError("File not found")

    with patch("frontmatter.load", side_effect=OSError("File not found")):
        with pytest.raises(AuthorExtractionError):
            extract_authors_from_post(mock_file)


def create_post(path: Path, frontmatter: dict[str, Any]) -> None:
    """Helper to create a markdown file with YAML frontmatter."""
    content = f"---\n{yaml.dump(frontmatter)}---\n\nHello World."
    path.write_text(dedent(content), encoding="utf-8")


@pytest.fixture
def project_structure(tmp_path: Path) -> tuple[Path, Path]:
    """Creates a standard docs/posts/posts project structure."""
    posts_dir = tmp_path / "docs" / "posts" / "posts"
    posts_dir.mkdir(parents=True)
    docs_dir = tmp_path / "docs"
    return docs_dir, posts_dir


def test_sync_authors_from_posts_with_new_authors(project_structure: tuple[Path, Path]) -> None:
    """Verify new authors from posts are added to .authors.yml."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.write_text(yaml.dump({"existing_author": {"name": "Existing"}}), "utf-8")

    create_post(posts_dir / "post1.md", {"authors": ["new_author_1"]})
    create_post(posts_dir / "post2.md", {"authors": ["new_author_2", "existing_author"]})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 2
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "new_author_1" in data
        assert "new_author_2" in data
        assert data["new_author_1"]["name"] == "new_author_1"
        assert data["new_author_2"]["url"] == "profiles/new_author_2.md"
        assert "existing_author" in data


def test_sync_authors_from_posts_no_new_authors(project_structure: tuple[Path, Path]) -> None:
    """Verify it returns 0 and makes no changes if no new authors are found."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    initial_content = yaml.dump({"author1": {"name": "Author One"}})
    authors_yml.write_text(initial_content, "utf-8")

    create_post(posts_dir / "post1.md", {"authors": ["author1"]})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 0
    assert authors_yml.read_text("utf-8") == initial_content


def test_sync_authors_from_posts_no_authors_yml(project_structure: tuple[Path, Path]) -> None:
    """Verify it creates .authors.yml if it doesn't exist."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"

    create_post(posts_dir / "post1.md", {"authors": ["author1", "author2"]})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 2
    assert authors_yml.exists()
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "author1" in data


def test_ensure_author_entries_adds_new_authors(project_structure: tuple[Path, Path]) -> None:
    """Verify ensure_author_entries adds new authors and preserves existing ones."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.write_text(yaml.dump({"existing_author": {"name": "Existing"}}), "utf-8")

    # The 'output_dir' argument is the posts_dir
    ensure_author_entries(posts_dir, ["new_author_1", "existing_author", "new_author_2"])

    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "new_author_1" in data
        assert "new_author_2" in data
        assert data["new_author_1"]["name"] == "new_author_1"
        assert "existing_author" in data
        assert len(data) == 3


def test_ensure_author_entries_creates_file(project_structure: tuple[Path, Path]) -> None:
    """Verify ensure_author_entries creates .authors.yml if it doesn't exist."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    assert not authors_yml.exists()

    ensure_author_entries(posts_dir, ["author1"])

    assert authors_yml.exists()
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "author1" in data


def test_ensure_author_entries_with_no_authors(
    project_structure: tuple[Path, Path], caplog: LogCaptureFixture
) -> None:
    """Verify it does nothing if the author list is empty or None."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    initial_content = yaml.dump({"existing": {"name": "Test"}})
    authors_yml.write_text(initial_content, "utf-8")

    # Test with empty list
    ensure_author_entries(posts_dir, [])
    assert authors_yml.read_text("utf-8") == initial_content
    assert "Registered 0 new author(s)" not in caplog.text

    # Test with None
    ensure_author_entries(posts_dir, None)
    assert authors_yml.read_text("utf-8") == initial_content
    assert "Registered 0 new author(s)" not in caplog.text


def test_sync_authors_from_posts_single_author_string(project_structure: tuple[Path, Path]) -> None:
    """Verify it correctly handles 'authors' as a single string, not a list."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.touch()

    create_post(posts_dir / "post1.md", {"authors": "string_author"})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 1
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "string_author" in data


def test_sync_authors_from_posts_no_author_metadata(
    project_structure: tuple[Path, Path], caplog: LogCaptureFixture
) -> None:
    """Verify it handles posts with no 'authors' key gracefully."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.touch()

    create_post(posts_dir / "post1.md", {"title": "A post with no author"})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 0
    assert "Synced 0 new author(s)" not in caplog.text


def test_sync_authors_from_posts_empty_authors_yml(project_structure: tuple[Path, Path]) -> None:
    """Verify it works correctly when .authors.yml is completely empty."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.write_text("", "utf-8")

    create_post(posts_dir / "post1.md", {"authors": ["author1"]})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 1
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "author1" in data
