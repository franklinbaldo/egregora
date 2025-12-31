from __future__ import annotations

from egregora.llm.token_utils import estimate_tokens


def test_estimate_tokens():
    """Test that estimate_tokens returns a reasonable approximation."""
    # Test with a simple string
    text1 = "This is a test string."
    assert estimate_tokens(text1) == len(text1) // 4

    # Test with a string that is not perfectly divisible by 4
    text2 = "This is another test string."
    assert estimate_tokens(text2) == len(text2) // 4

    # Test with an empty string
    text3 = ""
    assert estimate_tokens(text3) == 0

    # Test with a long string
    text4 = "a" * 1000
    assert estimate_tokens(text4) == 250


def test_estimate_tokens_typical_string():
    """Verify a typical string is estimated correctly."""
    assert estimate_tokens("one two three four") == 4


def test_estimate_tokens_non_multiple_length():
    """Verify a string with length not a multiple of 4 is handled."""
    assert estimate_tokens("abc") == 0


def test_estimate_tokens_multiple_length():
    """Verify a string with length as a multiple of 4 is handled."""
    assert estimate_tokens("abcd") == 1
