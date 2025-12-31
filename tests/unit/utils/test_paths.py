"""Behavioral tests for path utilities - focusing on slugify function.

Tests the slugify function behavior to ensure compatibility with MkDocs/Python Markdown.
Using TDD approach to document expected behavior before refactoring.
"""

from pathlib import Path

import pytest

from egregora.utils.paths import PathTraversalError, safe_path_join


def test_safe_path_join_valid(tmp_path: Path):
    """Tests a valid, simple path join."""
    result = safe_path_join(tmp_path, "posts", "my-article.md")
    expected = tmp_path.resolve() / "posts" / "my-article.md"
    assert result == expected


def test_safe_path_join_traversal_simple(tmp_path: Path):
    """Tests that a simple path traversal attack is blocked."""
    with pytest.raises(PathTraversalError, match="Path traversal detected"):
        safe_path_join(tmp_path, "..")


def test_safe_path_join_traversal_nested(tmp_path: Path):
    """Tests that a nested path traversal attack is blocked."""
    with pytest.raises(PathTraversalError, match="Path traversal detected"):
        safe_path_join(tmp_path, "posts", "../../etc/passwd")


def test_safe_path_join_absolute_path(tmp_path: Path):
    """Tests that joining an absolute path is blocked."""
    with pytest.raises(PathTraversalError, match="Absolute paths not allowed"):
        safe_path_join(tmp_path, "/etc/passwd")


def test_safe_path_join_empty_part(tmp_path: Path):
    """Tests that empty parts are handled correctly."""
    result = safe_path_join(tmp_path, "a", "", "b.txt")
    expected = tmp_path.resolve() / "a" / "b.txt"
    assert result == expected


def test_safe_path_join_current_dir(tmp_path: Path):
    """Tests that '.' parts are handled correctly."""
    result = safe_path_join(tmp_path, "a", ".", "b.txt")
    expected = tmp_path.resolve() / "a" / "b.txt"
    assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
