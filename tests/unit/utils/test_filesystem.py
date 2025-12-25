from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from egregora.utils.filesystem import _resolve_filepath, format_frontmatter_datetime


def test_resolve_filepath_no_collision(tmp_path: Path):
    """Verify it returns the original slug and path when no file exists."""
    output_dir = tmp_path
    date_prefix = "2025-01-01"
    base_slug = "my-post"

    filepath, slug = _resolve_filepath(output_dir, date_prefix, base_slug)

    assert slug == base_slug
    assert filepath.name == f"{date_prefix}-{base_slug}.md"
    assert not filepath.exists()


def test_resolve_filepath_handles_collision(tmp_path: Path):
    """Verify it appends a numeric suffix if a file exists."""
    output_dir = tmp_path
    date_prefix = "2025-01-01"
    base_slug = "my-post"
    filename = f"{date_prefix}-{base_slug}.md"

    # Create an initial file
    (output_dir / filename).touch()

    # The first resolution should append '-2'
    filepath, slug = _resolve_filepath(output_dir, date_prefix, base_slug)
    assert slug == f"{base_slug}-2"
    assert filepath.name == f"{date_prefix}-{slug}.md"

    # Create the new file
    filepath.touch()

    # The second resolution should append '-3'
    filepath_3, slug_3 = _resolve_filepath(output_dir, date_prefix, base_slug)
    assert slug_3 == f"{base_slug}-3"
    assert filepath_3.name == f"{date_prefix}-{slug_3}.md"


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
