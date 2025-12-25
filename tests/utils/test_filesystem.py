"""Tests for filesystem utilities."""

from __future__ import annotations

from pathlib import Path

from egregora.utils.filesystem import _find_authors_yml


def test_find_authors_yml_standard_layout(tmp_path: Path) -> None:
    """Verify it finds .authors.yml in a standard docs layout."""
    # Arrange
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    posts_dir.mkdir(parents=True)
    expected_path = docs_dir / ".authors.yml"
    expected_path.touch()

    # Act
    result = _find_authors_yml(posts_dir)

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
    result = _find_authors_yml(deep_dir)

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
    result = _find_authors_yml(output_dir)

    # Assert
    assert result == expected_path
