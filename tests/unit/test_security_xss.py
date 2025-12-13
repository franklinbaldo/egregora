"""Tests for security enhancements."""

import pytest
from egregora.input_adapters.whatsapp.parsing import _normalize_text

def test_normalize_text_escapes_html_tags():
    """Verify that potentially dangerous HTML tags are escaped during normalization."""
    # Test case: Malicious script tag
    malicious_input = "<script>alert(1)</script>"
    expected_output = "&lt;script&gt;alert(1)&lt;/script&gt;"

    # Assert
    assert _normalize_text(malicious_input) == expected_output

def test_normalize_text_escapes_partial_html():
    """Verify that partial or broken HTML-like sequences are also escaped."""
    # Test case: Unclosed tag
    input_text = "Look at this <img src=x onerror=alert(1)"
    expected_output = "Look at this &lt;img src=x onerror=alert(1)"

    assert _normalize_text(input_text) == expected_output

def test_normalize_text_preserves_quotes_by_default():
    """Verify that quotes are NOT escaped to maintain readability."""
    # We choose not to escape quotes in text content as it degrades readability
    # and is less risky in the Markdown body context than tags.
    input_text = 'Use "quotes" and \'single quotes\''
    expected_output = 'Use "quotes" and \'single quotes\''

    assert _normalize_text(input_text) == expected_output

def test_normalize_text_combined_normalization_and_escaping():
    """Verify that unicode normalization and HTML escaping work together."""
    # \u202f is Narrow No-Break Space, which NFKC normalizes to space
    input_text = "Hello\u202f<world>"
    expected_output = "Hello &lt;world&gt;"

    assert _normalize_text(input_text) == expected_output

def test_normalize_text_safe_input_remains_unchanged():
    """Verify that safe text is not modified."""
    input_text = "Just some normal text 123."
    assert _normalize_text(input_text) == input_text
