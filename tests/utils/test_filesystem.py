"""Tests for filesystem utilities."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from egregora.utils.authors import find_authors_yml
from egregora.utils.filesystem import (
    _extract_clean_date,
    _resolve_filepath,
)


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


def test_resolve_filepath_handles_collisions(tmp_path: Path) -> None:
    """Verify _resolve_filepath correctly appends a suffix to avoid collisions."""
    # Arrange
    output_dir = tmp_path / "posts"
    output_dir.mkdir()
    date_prefix = "2025-01-01"
    base_slug = "my-post"

    # Create a file that will cause a collision
    (output_dir / f"{date_prefix}-{base_slug}.md").touch()
    (output_dir / f"{date_prefix}-{base_slug}-2.md").touch()

    # Act: The function should now resolve to the next available suffix, which is 3
    resolved_path, final_slug = _resolve_filepath(output_dir, date_prefix, base_slug)

    # Assert
    assert final_slug == f"{base_slug}-3"
    assert resolved_path == output_dir / f"{date_prefix}-{final_slug}.md"
    assert (output_dir / f"{date_prefix}-{base_slug}.md").exists()  # Should not overwrite


@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        # Object Inputs
        (date(2023, 1, 15), "2023-01-15"),
        (datetime(2023, 1, 15, 10, 30), "2023-01-15"),
        # Valid String Inputs
        ("2023-01-15", "2023-01-15"),
        ("  2023-01-15  ", "2023-01-15"),
        # Valid String with surrounding text
        ("prefix-2023-01-15-suffix", "2023-01-15"),
        ("Date: 2023-01-15", "2023-01-15"),
        # Invalid but date-like strings (should pass through)
        ("2023-99-99", "2023-99-99"),
        ("not-a-date-2023-13-40", "not-a-date-2023-13-40"),
        # Non-date strings (should pass through)
        ("random string", "random string"),
        ("2023-01-15-invalid-date", "2023-01-15"),
    ],
)
def test_extract_clean_date(input_val, expected):
    """Verify _extract_clean_date handles various inputs correctly."""
    assert _extract_clean_date(input_val) == expected


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
