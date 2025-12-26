"""Tests for filesystem utilities."""

from __future__ import annotations

from pathlib import Path

import frontmatter
import yaml

from egregora.utils.authors import (
    find_authors_yml,
    sync_authors_from_posts,
)


def _create_post(path: Path, authors: list[str] | None = None) -> None:
    """Helper to create a markdown file with authors in frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(content=f"Content for {path.stem}", authors=authors or [])
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def test_sync_authors_from_posts_standard_layout(tmp_path: Path) -> None:
    """Verify it syncs authors in a standard `docs/posts` layout."""
    # Arrange
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    authors_path = docs_dir / ".authors.yml"
    _create_post(posts_dir / "post1.md", authors=["author-one"])
    _create_post(posts_dir / "post2.md", authors=["author-two"])

    # Act
    new_count = sync_authors_from_posts(posts_dir)

    # Assert
    assert new_count == 2
    assert authors_path.exists()
    authors_data = yaml.safe_load(authors_path.read_text())
    assert "author-one" in authors_data
    assert "author-two" in authors_data


def test_sync_authors_from_posts_fallback_layout(tmp_path: Path) -> None:
    """Verify it syncs authors using the fallback path resolution."""
    # Arrange
    posts_dir = tmp_path / "output" / "posts"
    # The fallback path is output_dir.parent.parent / ".authors.yml"
    authors_path = tmp_path / ".authors.yml"
    _create_post(posts_dir / "post1.md", authors=["author-one"])

    # Act
    new_count = sync_authors_from_posts(posts_dir)

    # Assert
    assert new_count == 1
    assert authors_path.exists()
    authors_data = yaml.safe_load(authors_path.read_text())
    assert "author-one" in authors_data


def test_sync_authors_from_posts_no_authors(tmp_path: Path) -> None:
    """Verify it does nothing if posts have no authors."""
    # Arrange
    posts_dir = tmp_path / "docs" / "posts"
    authors_path = tmp_path / "docs" / ".authors.yml"
    _create_post(posts_dir / "post1.md", authors=None)

    # Act
    new_count = sync_authors_from_posts(posts_dir)

    # Assert
    assert new_count == 0
    assert not authors_path.exists()


def test_find_authors_yml_standard_layout(tmp_path: Path) -> None:
    """Verify it finds .authors.yml in a standard docs layout."""
    # Arrange
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    posts_dir.mkdir(parents=True)
    expected_path = docs_dir / ".authors.yml"
    expected_path.touch()

    # Act
    result = find_authors_yml(posts_dir)

    # Assert
    assert result == expected_path


def test_find_authors_yml_nested_layout(tmp_path: Path) -> None:
    """Verify it finds .authors.yml from a deeper path."""
    # Arrange
    docs_dir = tmp_path / "site" / "docs"
    deep_dir = docs_dir / "section" / "posts"
    deep_dir.mkdir(parents=True)
    expected_path = docs_dir / ".authors.yml"
    expected_path.touch()

    # Act
    result = find_authors_yml(deep_dir)

    # Assert
    assert result == expected_path


def test_find_authors_yml_fallback_behavior(tmp_path: Path) -> None:
    """Verify it falls back to the legacy path if 'docs' is not found."""
    # Arrange
    output_dir = tmp_path / "output" / "posts"
    output_dir.mkdir(parents=True)
    # Fallback path is output_dir.parent.parent / ".authors.yml"
    expected_path = tmp_path / ".authors.yml"
    expected_path.touch()

    # Act
    result = find_authors_yml(output_dir)

    # Assert
    assert result == expected_path
