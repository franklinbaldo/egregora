"""Tests for V3 utility functions."""

from egregora_v3.core.utils import slugify


def test_slugify_basic():
    """Test basic slugification."""
    assert slugify("Hello World") == "hello-world"


def test_slugify_unicode():
    """Test unicode normalization."""
    assert slugify("Café") == "cafe"


def test_slugify_special_chars():
    """Test special character removal."""
    assert slugify("hello@world.com") == "hello-world-com"


def test_slugify_length_limit():
    """Test length limiting."""
    long_text = "a" * 100
    slug = slugify(long_text, max_len=10)
    assert len(slug) == 10
    assert slug == "a" * 10


def test_slugify_empty():
    """Test empty string handling."""
    assert slugify("") == "untitled"


def test_slugify_consecutive_separators():
    """Test consecutive separators are collapsed."""
    assert slugify("hello---world") == "hello-world"
