"""Tests for Jinja2 custom filters.

Following TDD - these tests will fail until the filters are extracted.
"""

from datetime import UTC, datetime

import pytest

from egregora_v3.engine.filters import (
    format_datetime,
    isoformat,
    truncate_words,
)


@pytest.mark.parametrize(
    ("value", "format_str", "expected"),
    [
        (datetime(2024, 7, 26, 10, 30, 0, tzinfo=UTC), "%Y-%m-%d", "2024-07-26"),
        (datetime(2024, 7, 26, 10, 30, 0, tzinfo=UTC), "%H:%M", "10:30"),
        ("not a date", "%Y", "not a date"),
        (None, "%Y", "None"),
    ],
)
def test_format_datetime(value: datetime | str | None, format_str: str, expected: str) -> None:
    """Test the format_datetime filter."""
    assert format_datetime(value, format_str) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2024, 7, 26, 10, 30, 0, tzinfo=UTC), "2024-07-26T10:30:00+00:00"),
        ("not a date", "not a date"),
        (None, "None"),
    ],
)
def test_isoformat(value: datetime | str | None, expected: str) -> None:
    """Test the isoformat filter."""
    assert isoformat(value) == expected


@pytest.mark.parametrize(
    ("value", "num_words", "suffix", "expected"),
    [
        ("one two three four five", 5, "...", "one two three four five"),
        ("one two three four five six", 5, "...", "one two three four five..."),
        ("one two", 5, "...", "one two"),
        ("", 5, "...", ""),
    ],
)
def test_truncate_words(value: str, num_words: int, suffix: str, expected: str) -> None:
    """Test the truncate_words filter."""
    assert truncate_words(value, num_words, suffix) == expected
