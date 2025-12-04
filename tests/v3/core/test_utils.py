"""Tests for V3 utility functions."""
import pytest


def test_slugify_basic():
    """Test basic slugification."""
    from egregora_v3.core.utils import slugify

    assert slugify("Hello World") == "hello-world"
    assert slugify("Hello World!", max_len=60) == "hello-world"

def test_slugify_unicode():
    """Test unicode normalization."""
    from egregora_v3.core.utils import slugify

    assert slugify("Café") == "cafe"
    assert slugify("naïve") == "naive"

def test_slugify_special_chars():
    """Test special character removal."""
    from egregora_v3.core.utils import slugify

    assert slugify("hello@world.com") == "hello-world-com"
    assert slugify("test_slug") == "test-slug"
    assert slugify("a/b/c") == "a-b-c"

def test_slugify_length_limit():
    """Test length limiting."""
    from egregora_v3.core.utils import slugify

    long_text = "a" * 100
    assert len(slugify(long_text, max_len=20)) <= 20
    assert slugify(long_text, max_len=20) == "a" * 20

def test_slugify_empty():
    """Test empty string handling."""
    from egregora_v3.core.utils import slugify

    assert slugify("") == "untitled"
    assert slugify("!!!") == "untitled"

def test_slugify_consecutive_separators():
    """Test consecutive separators are collapsed."""
    from egregora_v3.core.utils import slugify

    assert slugify("hello---world") == "hello-world"
    assert slugify("a  b  c") == "a-b-c"
