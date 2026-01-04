"""Tests for the V2 slugify utility function."""

import pytest

from egregora.core.exceptions import InvalidInputError
from egregora.utils.text import slugify


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

    def test_multiple_spaces_create_multiple_hyphens(self):
        """BEHAVIOR: Multiple spaces create corresponding hyphens (pymdownx behavior)."""
        # pymdownx.slugs preserves space-to-hyphen mapping
        assert slugify("Hello    World") == "hello----world"

    def test_leading_trailing_spaces_removed(self):
        """BEHAVIOR: Leading and trailing spaces are removed."""
        assert slugify("  Hello World  ") == "hello-world"

    def test_hyphens_preserved(self):
        """BEHAVIOR: Hyphens are preserved as-is (pymdownx behavior)."""
        assert slugify("hello-world") == "hello-world"
        assert slugify("hello---world") == "hello---world"  # Multiple hyphens preserved

    def test_underscores_preserved(self):
        """BEHAVIOR: Underscores are preserved in slugs (pymdownx behavior)."""
        assert slugify("hello_world") == "hello_world"


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
        # This should produce some ASCII representation
        result = slugify("Привет")
        assert result.isascii()
        assert len(result) > 0

    def test_chinese_characters_handled(self):
        """BEHAVIOR: Chinese characters handled gracefully."""
        result = slugify("你好")
        # Should produce valid slug (may be empty or transliterated)
        assert result.isascii()

    def test_mixed_unicode_and_ascii(self):
        """BEHAVIOR: Mixed Unicode and ASCII handled."""
        assert slugify("Café in München") == "cafe-in-munchen"

    def test_emoji_removed(self):
        """BEHAVIOR: Emoji are removed, but spaces between create hyphens."""
        result = slugify("Hello 👋 World 🌍")
        # Emoji removed, but the spaces remain as hyphens
        assert result == "hello--world"

    def test_nfkd_normalization_chars(self):
        """BEHAVIOR: Characters normalized by NFKD are handled."""
        # For example, the registered trademark symbol ® is stripped
        assert slugify("Registered®") == "registered"


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
        result = slugify("😀😀😀")
        assert result == "post"  # Falls back when nothing remains

    def test_none_input_raises_invalid_input_error(self):
        """BEHAVIOR: None input raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Input text cannot be None"):
            slugify(None)

    def test_numbers_preserved(self):
        """BEHAVIOR: Numbers are preserved in slugs."""
        assert slugify("Test 123") == "test-123"
        assert slugify("2024-01-15") == "2024-01-15"

    def test_dots_removed(self):
        """BEHAVIOR: Dots are removed (not converted to hyphens)."""
        assert slugify("file.name.txt") == "filenametxt"

    def test_slashes_removed(self):
        """BEHAVIOR: Slashes are removed (not converted to hyphens)."""
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
        # If truncation happens mid-word, trailing hyphen should be removed
        text = "a" * 25 + "-" + "b" * 50
        result = slugify(text, max_len=26)
        assert not result.endswith("-")
        assert len(result) <= 26

    def test_short_text_not_padded(self):
        """BEHAVIOR: Short text is not padded to max_len."""
        assert slugify("hi", max_len=60) == "hi"

    def test_text_shorter_than_max_len_is_not_truncated(self):
        """BEHAVIOR: Text shorter than max_len is not truncated."""
        text = "a" * 20
        result = slugify(text, max_len=30)
        assert result == text


class TestSlugifySecurity:
    """Test security-related behavior - path traversal protection."""

    def test_path_traversal_dots_removed(self):
        """BEHAVIOR: Path traversal patterns are sanitized (dots/slashes removed)."""
        assert slugify("../../etc/passwd") == "etcpasswd"

    def test_absolute_paths_sanitized(self):
        """BEHAVIOR: Absolute path markers are removed (slashes removed)."""
        assert slugify("/etc/passwd") == "etcpasswd"

    def test_backslashes_sanitized(self):
        """BEHAVIOR: Windows-style backslashes are removed."""
        assert slugify("..\\..\\windows\\system32") == "windowssystem32"

    def test_null_bytes_removed(self):
        """BEHAVIOR: Null bytes are removed."""
        result = slugify("hello\x00world")
        assert result == "helloworld"


class TestSlugifyConsistency:
    """Test consistency with MkDocs/Python Markdown behavior."""

    def test_matches_mkdocs_heading_slug_behavior(self):
        """BEHAVIOR: Should match MkDocs heading ID generation."""
        # MkDocs uses pymdownx.slugs internally for heading IDs
        # Our slugs should match that behavior
        assert slugify("Getting Started") == "getting-started"
        assert slugify("API Reference") == "api-reference"

    def test_idempotent_on_already_slugified(self):
        """BEHAVIOR: Running slugify twice produces same result."""
        original = "Hello World!"
        first = slugify(original)
        second = slugify(first)
        assert first == second

    def test_deterministic_output(self):
        """BEHAVIOR: Same input always produces same output."""
        text = "Complex Test Case 123"
        results = [slugify(text) for _ in range(10)]
        assert len(set(results)) == 1  # All identical


class TestSlugifyRealWorldExamples:
    """Test real-world examples from actual usage."""

    def test_blog_post_titles(self):
        """BEHAVIOR: Typical blog post titles."""
        assert slugify("How to Build a Web App") == "how-to-build-a-web-app"
        assert slugify("Top 10 Python Tips") == "top-10-python-tips"

    def test_technical_terms(self):
        """BEHAVIOR: Technical terminology."""
        assert slugify("REST API Design") == "rest-api-design"
        assert slugify("OAuth2.0 Authentication") == "oauth20-authentication"

    def test_author_names(self):
        """BEHAVIOR: Author names with various characters."""
        assert slugify("José García") == "jose-garcia"
        assert slugify("François Müller") == "francois-muller"

    def test_dates_in_titles(self):
        """BEHAVIOR: Dates embedded in titles."""
        assert slugify("2024-01-15 Release Notes") == "2024-01-15-release-notes"

    def test_markdown_style_slugs(self):
        """BEHAVIOR: Already hyphenated markdown-style text."""
        assert slugify("my-existing-slug") == "my-existing-slug"
