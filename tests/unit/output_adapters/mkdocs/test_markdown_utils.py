"""Tests for the markdown utilities."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from egregora.output_sinks.mkdocs.markdown_utils import (
    DateExtractionError,
    FrontmatterDateFormattingError,
    extract_clean_date,
    format_frontmatter_datetime,
)


# region: Tests for extract_clean_date
def test_extract_clean_date_with_datetime():
    assert extract_clean_date(datetime(2023, 1, 1, 12, 30)) == "2023-01-01"


def test_extract_clean_date_with_date():
    assert extract_clean_date(date(2023, 1, 1)) == "2023-01-01"


def test_extract_clean_date_with_string():
    assert extract_clean_date("2023-01-01") == "2023-01-01"


def test_extract_clean_date_with_string_and_time():
    assert extract_clean_date("2023-01-01 12:30") == "2023-01-01"


def test_extract_clean_date_raises_on_no_date_in_string():
    with pytest.raises(DateExtractionError):
        extract_clean_date("hello world")


def test_extract_clean_date_raises_error_on_invalid_date():
    """Verify that extract_clean_date raises DateExtractionError for invalid dates."""
    invalid_date_str = "2023-99-99"
    with pytest.raises(DateExtractionError) as excinfo:
        extract_clean_date(invalid_date_str)

    assert "Could not extract a valid date" in str(excinfo.value)
    assert invalid_date_str in str(excinfo.value)


def test_extract_clean_date_raises_on_none():
    """Verify that extract_clean_date raises an error on None input."""
    with pytest.raises(DateExtractionError) as excinfo:
        extract_clean_date(None)
    assert "Could not extract a valid date" in str(excinfo.value)
    assert "None" in str(excinfo.value)


VALID_DATE_INPUTS = [
    ("2023-01-15", "2023-01-15"),
    (date(2023, 1, 15), "2023-01-15"),
    (datetime(2023, 1, 15, 10, 30), "2023-01-15"),
    ("  2023-01-15T10:30:00Z  ", "2023-01-15"),
    ("Some text surrounding 2023-01-15 and other things", "2023-01-15"),
]


@pytest.mark.benchmark(group="extract-clean-date")
@pytest.mark.parametrize(("input_date", "expected"), VALID_DATE_INPUTS)
def test_extract_clean_date_benchmark(benchmark, input_date, expected):
    """Benchmark the extract_clean_date function."""
    result = benchmark(extract_clean_date, input_date)
    assert result == expected


# endregion


# region: Tests for format_frontmatter_datetime
def test_format_frontmatter_datetime_raises_on_invalid_date():
    with pytest.raises(FrontmatterDateFormattingError):
        format_frontmatter_datetime("invalid-date")


def test_format_frontmatter_datetime_raises_on_none():
    """Verify that format_frontmatter_datetime raises an error on None input."""
    with pytest.raises(FrontmatterDateFormattingError) as excinfo:
        format_frontmatter_datetime(None)

    assert "Failed to parse date string for frontmatter: 'None'" in str(excinfo.value)


def test_format_frontmatter_datetime_handles_ranges():
    """Verify that format_frontmatter_datetime handles date ranges by using the start time."""
    input_date = "2025-10-28 14:10 to 14:15"
    expected = "2025-10-28 14:10"
    assert format_frontmatter_datetime(input_date) == expected


# endregion
