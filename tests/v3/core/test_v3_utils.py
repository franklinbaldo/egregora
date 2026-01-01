
import pytest
from egregora_v3.core.utils import simple_chunk_text, slugify


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
    assert len(chunks) == 3
    assert chunks[0] == "one two three four"
    assert chunks[1] == "three four five six"
    assert chunks[2] == "six seven eight nine ten"


class TestSlugifyV3:
    """Tests for the V3 slugify function, now compatible with V2."""

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
        assert slugify("Hello    World") == "hello----world"

    def test_leading_trailing_spaces_removed(self):
        """BEHAVIOR: Leading and trailing spaces are removed."""
        assert slugify("  Hello World  ") == "hello-world"

    def test_hyphens_preserved(self):
        """BEHAVIOR: Hyphens are preserved as-is (pymdownx behavior)."""
        assert slugify("hello-world") == "hello-world"
        assert slugify("hello---world") == "hello---world"

    def test_underscores_preserved(self):
        """BEHAVIOR: Underscores are preserved in slugs (pymdownx behavior)."""
        assert slugify("hello_world") == "hello_world"

    def test_french_accents_transliterated(self):
        """BEHAVIOR: French accented characters become ASCII equivalents."""
        assert slugify("Café") == "cafe"
        assert slugify("élève") == "eleve"
        assert slugify("à Paris") == "a-paris"

    def test_empty_string_returns_fallback(self):
        """BEHAVIOR: Empty string returns fallback value 'post'."""
        assert slugify("") == "post"

    def test_only_special_characters_returns_fallback(self):
        """BEHAVIOR: String with only special characters returns fallback."""
        assert slugify("!!!???") == "post"

    def test_respects_max_length(self):
        """BEHAVIOR: Custom max_len parameter works."""
        long_text = "a" * 100
        result = slugify(long_text, max_len=20)
        assert len(result) == 20
        assert result == "a" * 20

    def test_truncation_removes_trailing_hyphens(self):
        """BEHAVIOR: Truncation removes trailing hyphens."""
        text = "a" * 25 + "-" + "b" * 50
        result = slugify(text, max_len=26)
        assert not result.endswith("-")

    def test_path_traversal_sanitized(self):
        """BEHAVIOR: Path traversal patterns are sanitized."""
        assert slugify("../../etc/passwd") == "etcpasswd"
