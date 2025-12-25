from __future__ import annotations

from datetime import date, datetime

import pytest

from egregora.utils.filesystem import format_frontmatter_datetime


def test_format_frontmatter_datetime_with_none():
    """Verify that None input returns an empty string."""
    assert format_frontmatter_datetime(None) == ""


def test_format_frontmatter_datetime_with_datetime_object():
    """Verify that a datetime object is formatted correctly."""
    dt = datetime(2023, 1, 15, 10, 30)
    assert format_frontmatter_datetime(dt) == "2023-01-15 10:30"


def test_format_frontmatter_datetime_with_date_object():
    """Verify that a date object is formatted correctly."""
    d = date(2023, 1, 15)
    assert format_frontmatter_datetime(d) == "2023-01-15 00:00"


@pytest.mark.parametrize(
    ("date_str", "expected"),
    [
        ("2023-01-15", "2023-01-15 00:00"),
        ("2023-01-15 10:30", "2023-01-15 10:30"),
        ("Jan 15, 2023", "2023-01-15 00:00"),
    ],
)
def test_format_frontmatter_datetime_with_valid_string(date_str, expected):
    """Verify that valid date strings are parsed and formatted correctly."""
    assert format_frontmatter_datetime(date_str) == expected


@pytest.mark.parametrize(
    "invalid_str",
    [
        "not a date",
        "2023-99-99",
    ],
)
def test_format_frontmatter_datetime_with_unparseable_string(invalid_str):
    """Verify that unparseable strings are returned as-is."""
    assert format_frontmatter_datetime(invalid_str) == invalid_str


@pytest.mark.parametrize(
    "empty_str",
    [
        "",
        "  ",
    ],
)
def test_format_frontmatter_datetime_with_empty_string(empty_str):
    """Verify that empty or whitespace-only strings are returned as-is."""
    assert format_frontmatter_datetime(empty_str) == empty_str.strip()
