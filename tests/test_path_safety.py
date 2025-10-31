"""Tests for path safety utilities and write_post security."""

from pathlib import Path

import pytest

from egregora.utils import slugify, safe_path_join, PathTraversalError
from egregora.orchestration.write_post import write_post


class TestSlugify:
    """Tests for slugify function."""

    def test_basic_slugify(self):
        """Test basic ASCII text slugification."""
        assert slugify("Hello World") == "hello-world"
        assert slugify("This is a Test!") == "this-is-a-test"

    def test_unicode_normalization(self):
        """Test Unicode to ASCII normalization."""
        assert slugify("Café à Paris") == "cafe-a-paris"
        assert slugify("Résumé") == "resume"
        assert slugify("Naïve") == "naive"

    def test_special_characters(self):
        """Test removal of special characters."""
        assert slugify("Hello@World!") == "hello-world"
        assert slugify("test_file.txt") == "test-file-txt"
        assert slugify("one&two") == "one-two"

    def test_path_traversal_attempts(self):
        """Test that path traversal attempts are sanitized."""
        assert slugify("../../etc/passwd") == "etc-passwd"
        assert slugify("..\\..\\windows\\system32") == "windows-system32"
        assert slugify("/etc/shadow") == "etc-shadow"
        assert slugify("a/b/c") == "a-b-c"

    def test_consecutive_hyphens(self):
        """Test that consecutive hyphens are collapsed."""
        assert slugify("hello---world") == "hello-world"
        assert slugify("test__file") == "test-file"
        assert slugify("one  two  three") == "one-two-three"

    def test_max_length(self):
        """Test length truncation."""
        long_text = "a" * 100
        assert len(slugify(long_text, max_len=20)) == 20
        assert slugify(long_text, max_len=20) == "aaaaaaaaaaaaaaaaaaaa"

    def test_empty_and_fallback(self):
        """Test empty input and fallback to 'post'."""
        assert slugify("") == "post"
        assert slugify("!!!") == "post"
        assert slugify("@#$%") == "post"

    def test_emoji_removal(self):
        """Test that emojis are removed."""
        assert slugify("Hello 👋 World 🌍") == "hello-world"
        assert slugify("🔥🔥🔥") == "post"


class TestSafePathJoin:
    """Tests for safe_path_join function."""

    def test_basic_join(self, tmp_path):
        """Test basic path joining."""
        result = safe_path_join(tmp_path, "file.txt")
        assert result == tmp_path / "file.txt"

    def test_subdirectory_join(self, tmp_path):
        """Test joining with subdirectories."""
        result = safe_path_join(tmp_path, "subdir", "file.txt")
        assert result == tmp_path / "subdir" / "file.txt"

    def test_path_traversal_blocked(self, tmp_path):
        """Test that path traversal attempts are blocked."""
        with pytest.raises(PathTraversalError):
            safe_path_join(tmp_path, "../etc/passwd")

        with pytest.raises(PathTraversalError):
            safe_path_join(tmp_path, "../../etc/passwd")

        with pytest.raises(PathTraversalError):
            safe_path_join(tmp_path, "subdir/../../etc/passwd")

    def test_absolute_path_blocked(self, tmp_path):
        """Test that absolute paths that escape base are blocked."""
        with pytest.raises(PathTraversalError):
            safe_path_join(tmp_path, "/etc/passwd")

    def test_windows_path_traversal(self, tmp_path):
        """Test Windows-style path traversal attempts are blocked on POSIX.

        Critical security test: On POSIX systems, backslashes are valid filename
        characters. Without normalization, "..\\..\\windows\\system32" would create
        a file literally named "..\\..\\windows\\system32" instead of traversing
        directories, bypassing our security checks.

        This test verifies that backslashes are normalized to forward slashes
        before path validation, preventing cross-platform bypass attacks.
        """
        # Test simple Windows-style traversal
        with pytest.raises(PathTraversalError):
            safe_path_join(tmp_path, "..\\..\\windows\\system32")

        # Test mixed separators
        with pytest.raises(PathTraversalError):
            safe_path_join(tmp_path, "..\\../etc/passwd")

        # Test Windows absolute paths with backslashes
        with pytest.raises(PathTraversalError):
            safe_path_join(tmp_path, "C:\\windows\\system32")

        # Test deep Windows-style traversal
        with pytest.raises(PathTraversalError):
            safe_path_join(tmp_path, "..\\..\\..\\..\\..\\etc\\passwd")

    def test_backslash_normalization_in_safe_paths(self, tmp_path):
        """Test that backslashes in safe paths are normalized correctly.

        Verifies that legitimate Windows-style paths that don't escape
        the base directory are normalized to POSIX-style paths.
        """
        # A path with backslashes that doesn't escape should be normalized
        result = safe_path_join(tmp_path, "subdir\\file.txt")
        # Should normalize to forward slash
        assert result == tmp_path / "subdir" / "file.txt"


class TestWritePostSecurity:
    """Security tests for write_post function."""

    def test_slug_sanitization(self, tmp_path):
        """Test that slugs are sanitized before creating files."""
        output_dir = tmp_path / "posts"
        output_dir.mkdir()

        metadata = {
            "title": "Test Post",
            "slug": "../../etc/passwd",
            "date": "2025-01-01",
        }

        result_path = write_post("Test content", metadata, output_dir)
        result = Path(result_path)

        # Verify file was created in output_dir, not in /etc/
        assert result.parent == output_dir
        assert result.name == "2025-01-01-etc-passwd.md"

    def test_unicode_slug(self, tmp_path):
        """Test that Unicode slugs are normalized."""
        output_dir = tmp_path / "posts"
        output_dir.mkdir()

        metadata = {
            "title": "Café Post",
            "slug": "café-à-paris",
            "date": "2025-01-01",
        }

        result_path = write_post("Test content", metadata, output_dir)
        result = Path(result_path)

        assert result.parent == output_dir
        assert result.name == "2025-01-01-cafe-a-paris.md"

    def test_special_characters_in_slug(self, tmp_path):
        """Test that special characters are removed from slugs."""
        output_dir = tmp_path / "posts"
        output_dir.mkdir()

        metadata = {
            "title": "Test Post",
            "slug": "hello@world!test",
            "date": "2025-01-01",
        }

        result_path = write_post("Test content", metadata, output_dir)
        result = Path(result_path)

        assert result.name == "2025-01-01-hello-world-test.md"

    def test_duplicate_slug_handling(self, tmp_path):
        """Test that duplicate slugs get unique filenames."""
        output_dir = tmp_path / "posts"
        output_dir.mkdir()

        metadata = {
            "title": "Test Post",
            "slug": "test-post",
            "date": "2025-01-01",
        }

        # Create first post
        first_path = write_post("First content", metadata, output_dir)
        assert Path(first_path).name == "2025-01-01-test-post.md"

        # Create duplicate - should get -2 suffix
        second_path = write_post("Second content", metadata, output_dir)
        assert Path(second_path).name == "2025-01-01-test-post-2.md"

        # Create another duplicate - should get -3 suffix
        third_path = write_post("Third content", metadata, output_dir)
        assert Path(third_path).name == "2025-01-01-test-post-3.md"

    def test_empty_slug_fallback(self, tmp_path):
        """Test that empty slugs fall back to 'post'."""
        output_dir = tmp_path / "posts"
        output_dir.mkdir()

        metadata = {
            "title": "Test Post",
            "slug": "!!!",  # All special chars, will become empty
            "date": "2025-01-01",
        }

        result_path = write_post("Test content", metadata, output_dir)
        result = Path(result_path)

        assert result.name == "2025-01-01-post.md"

    def test_path_stays_in_output_dir(self, tmp_path):
        """Test that all paths stay within output_dir."""
        output_dir = tmp_path / "posts"
        output_dir.mkdir()

        dangerous_slugs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/etc/shadow",
            "a/b/c/d",
        ]

        for slug in dangerous_slugs:
            metadata = {
                "title": "Test",
                "slug": slug,
                "date": "2025-01-01",
            }

            result_path = write_post("Test", metadata, output_dir)
            result = Path(result_path)

            # Verify result is within output_dir
            assert result.parent == output_dir
            assert output_dir in result.parents or result.parent == output_dir
