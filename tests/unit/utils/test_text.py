from __future__ import annotations

from egregora.utils.text import estimate_tokens


def test_estimate_tokens_empty_string():
    """Verify empty string returns 0."""
    assert estimate_tokens("") == 0


def test_estimate_tokens_typical_string():
    """Verify a typical string is estimated correctly."""
    assert estimate_tokens("one two three four") == 4


def test_estimate_tokens_non_multiple_length():
    """Verify a string with length not a multiple of 4 is handled."""
    assert estimate_tokens("abc") == 0


def test_estimate_tokens_multiple_length():
    """Verify a string with length as a multiple of 4 is handled."""
    assert estimate_tokens("abcd") == 1
