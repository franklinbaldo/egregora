"""Tests for WhatsApp command utility functions."""

import ibis
import pytest

from src.egregora.input_adapters.whatsapp.commands import normalize_smart_quotes, strip_wrapping_quotes


@pytest.fixture(scope="module")
def con():
    """Ibis DuckDB connection fixture."""
    return ibis.duckdb.connect()


def test_normalize_smart_quotes(con):
    """Verify that smart quotes are replaced with standard quotes via Ibis."""
    test_cases = {
        "‘Hello’ “World”": "'Hello' \"World\"",
        "’Tis a test’": "'Tis a test'",
        "“Straight quotes are fine”": "\"Straight quotes are fine\"",
        "No quotes here": "No quotes here",
        None: None,  # A None input should result in a None output
    }
    for input_str, expected in test_cases.items():
        expr = ibis.literal(input_str, type="string").pipe(normalize_smart_quotes)
        result = con.execute(expr)
        # DuckDB returns None for NULL string operations, which is the correct DB behavior.
        assert result is None if input_str is None else result == expected


def test_strip_wrapping_quotes(con):
    """Verify that wrapping quotes are stripped from a string via Ibis."""
    test_cases = {
        '"Hello"': "Hello",
        "'World'": "World",
        "No quotes": "No quotes",
        '"Mismatched\'': '"Mismatched\'',
        None: None,
    }
    for input_str, expected in test_cases.items():
        expr = ibis.literal(input_str, type="string").pipe(strip_wrapping_quotes)
        result = con.execute(expr)
        assert result is None if input_str is None else result == expected
