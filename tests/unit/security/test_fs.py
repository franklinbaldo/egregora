"""Unit tests for filesystem security utilities."""

from pathlib import Path

import pytest

from egregora.security.fs import PathTraversalError, safe_path_join


def test_safe_path_join_allows_valid_paths(tmp_path):
    """Test that safe_path_join correctly joins valid, non-malicious paths."""
    base_dir = tmp_path
    result = safe_path_join(base_dir, "foo", "bar", "baz.txt")
    assert result == base_dir / "foo" / "bar" / "baz.txt"


def test_safe_path_join_prevents_directory_traversal_with_dots(tmp_path):
    """Test that safe_path_join prevents climbing up the directory tree."""
    base_dir = tmp_path
    with pytest.raises(PathTraversalError):
        safe_path_join(base_dir, "..", "etc", "passwd")


def test_safe_path_join_prevents_traversal_with_absolute_paths(tmp_path):
    """Test that safe_path_join rejects absolute paths in the parts."""
    base_dir = tmp_path
    with pytest.raises(PathTraversalError):
        safe_path_join(base_dir, "/etc/passwd")


def test_safe_path_join_handles_nested_traversals(tmp_path):
    """Test that safe_path_join can detect traversals buried in subdirectories."""
    base_dir = tmp_path
    with pytest.raises(PathTraversalError):
        safe_path_join(base_dir, "foo", "bar", "..", "..", "..", "etc", "passwd")


def test_safe_path_join_allows_paths_within_the_base_directory(tmp_path):
    """Test that it correctly handles paths that are within the base directory."""
    base_dir = tmp_path
    (base_dir / "foo").mkdir()
    result = safe_path_join(base_dir, "foo", "..", "foo", "bar.txt")
    assert result == base_dir / "foo" / "bar.txt"


def test_safe_path_join_with_empty_parts(tmp_path):
    """Test that safe_path_join works correctly with empty path parts."""
    base_dir = tmp_path
    result = safe_path_join(base_dir)
    assert result == base_dir


def test_safe_path_join_raises_error_on_complex_traversal(tmp_path: Path) -> None:
    """Test a more complex path traversal attempt."""
    with pytest.raises(PathTraversalError):
        # This path resolves to <tmp_path>/../d, which is outside the base directory.
        safe_path_join(tmp_path, "a/b/c", "../../../../d")
