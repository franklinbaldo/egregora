"""Behavioral tests for path utilities - focusing on slugify function."""

from pathlib import Path

import pytest

from egregora_v3.core.utils import (
    PathTraversalError,
    safe_path_join,
    simple_chunk_text,
    slugify,
)


class TestSlugifyBasicBehavior:
    """Test basic slugification behavior - converting text to URL-safe slugs."""

    def test_simple_text_becomes_lowercase_hyphenated(self):
        """BEHAVIOR: Simple text is lowercased and spaces become hyphens."""
        assert slugify("Hello World") == "hello-world"

    def test_preserves_case_when_lowercase_false(self):
        """BEHAVIOR: Can preserve case when lowercase=False."""
        assert slugify("Hello World", lowercase=False) == "Hello-World"

    def test_removes_special_characters(self):
        """BEHAVIOR: Special characters are removed."""
        assert slugify("Hello, World!") == "hello-world"
        assert slugify("Test@Example#Hash") == "testexamplehash"

    def test_multiple_spaces_are_condensed(self):
        """BEHAVIOR: Multiple spaces are condensed to a single hyphen."""
        assert slugify("Hello    World") == "hello-world"

    def test_leading_trailing_spaces_removed(self):
        """BEHAVIOR: Leading and trailing spaces are removed."""
        assert slugify("  Hello World  ") == "hello-world"

    def test_hyphens_preserved_and_condensed(self):
        """BEHAVIOR: Hyphens are preserved and condensed."""
        assert slugify("hello-world") == "hello-world"
        assert slugify("hello---world") == "hello-world"

    def test_underscores_are_removed(self):
        """BEHAVIOR: Underscores are removed."""
        assert slugify("hello_world") == "helloworld"


class TestSlugifyUnicode:
    """Test Unicode handling - transliteration to ASCII."""

    def test_french_accents_transliterated(self):
        """BEHAVIOR: French accented characters become ASCII equivalents."""
        assert slugify("Café") == "cafe"
        assert slugify("élève") == "eleve"
        assert slugify("à Paris") == "a-paris"

    def test_german_characters_transliterated(self):
        """BEHAVIOR: German special characters transliterated."""
        assert slugify("Über") == "uber"
        assert slugify("Müller") == "muller"

    def test_cyrillic_transliterated(self):
        """BEHAVIOR: Cyrillic characters transliterated to ASCII."""
        result = slugify("Привет")
        assert result.isascii()
        assert result == "privet"

    def test_chinese_characters_handled(self):
        """BEHAVIOR: Chinese characters are removed, resulting in fallback."""
        assert slugify("你好") == "post"

    def test_mixed_unicode_and_ascii(self):
        """BEHAVIOR: Mixed Unicode and ASCII handled."""
        assert slugify("Café in München") == "cafe-in-munchen"

    def test_emoji_removed(self):
        """BEHAVIOR: Emoji are removed."""
        assert slugify("Hello 👋 World 🌍") == "hello-world"


class TestSlugifyEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_returns_fallback(self):
        """BEHAVIOR: Empty string returns fallback value 'post'."""
        assert slugify("") == "post"

    def test_only_special_characters_returns_fallback(self):
        """BEHAVIOR: String with only special characters returns fallback."""
        assert slugify("!!!???") == "post"

    def test_only_unicode_that_strips_returns_fallback(self):
        """BEHAVIOR: String with only non-transliteratable Unicode returns fallback."""
        assert slugify("😀😀😀") == "post"

    def test_numbers_preserved(self):
        """BEHAVIOR: Numbers are preserved in slugs."""
        assert slugify("Test 123") == "test-123"
        assert slugify("2024-01-15") == "2024-01-15"

    def test_dots_removed(self):
        """BEHAVIOR: Dots are removed."""
        assert slugify("file.name.txt") == "filenametxt"

    def test_slashes_removed(self):
        """BEHAVIOR: Slashes are removed."""
        assert slugify("path/to/file") == "pathtofile"


class TestSlugifyMaxLength:
    """Test maximum length truncation behavior."""

    def test_respects_max_length_default_60(self):
        """BEHAVIOR: Default max_len is 60 characters."""
        long_text = "a" * 100
        result = slugify(long_text)
        assert len(result) == 60

    def test_respects_custom_max_length(self):
        """BEHAVIOR: Custom max_len parameter works."""
        long_text = "a" * 100
        result = slugify(long_text, max_len=20)
        assert len(result) == 20

    def test_truncation_removes_trailing_hyphens(self):
        """BEHAVIOR: Truncation removes trailing hyphens."""
        text = "a" * 25 + "-" + "b" * 50
        result = slugify(text, max_len=26)
        assert not result.endswith("-")
        assert len(result) <= 26

    def test_short_text_not_padded(self):
        """BEHAVIOR: Short text is not padded to max_len."""
        assert slugify("hi", max_len=60) == "hi"


class TestSlugifySecurity:
    """Test security-related behavior - path traversal protection."""

    def test_path_traversal_dots_removed(self):
        """BEHAVIOR: Path traversal patterns are sanitized."""
        assert slugify("../../etc/passwd") == "etcpasswd"

    def test_absolute_paths_sanitized(self):
        """BEHAVIOR: Absolute path markers are removed."""
        assert slugify("/etc/passwd") == "etcpasswd"

    def test_backslashes_sanitized(self):
        """BEHAVIOR: Windows-style backslashes are removed."""
        assert slugify("..\\..\\windows\\system32") == "windowssystem32"

    def test_null_bytes_removed(self):
        """BEHAVIOR: Null bytes are removed."""
        assert slugify("hello\x00world") == "helloworld"


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

import pytest
from egregora_v3.core.utils import simple_chunk_text


def test_simple_chunk_text_empty():
    assert simple_chunk_text("") == []


def test_simple_chunk_text_short():
    text = "This is a short text."
    assert simple_chunk_text(text, max_chars=100) == [text]


def test_simple_chunk_text_long():
    text = "This is a long text that should be split into multiple chunks."
    chunks = simple_chunk_text(text, max_chars=20, overlap=5)
    assert len(chunks) > 1
    assert chunks[0] == "This is a long text"
    assert "text that should be" in chunks[1]


def test_simple_chunk_text_exact_multiple():
    text = "word " * 20
    chunks = simple_chunk_text(text.strip(), max_chars=50, overlap=10)
    assert len(chunks) > 1


def test_simple_chunk_text_with_overlap():
    text = "one two three four five six seven eight nine ten"
    chunks = simple_chunk_text(text, max_chars=20, overlap=10)
    assert len(chunks) == 4
    assert chunks[0] == "one two three four"
    assert chunks[1] == "four five six seven"
    assert chunks[2] == "six seven eight"
    assert chunks[3] == "eight nine ten"
