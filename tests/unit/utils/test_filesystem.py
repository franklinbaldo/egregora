"""Unit tests for filesystem utilities."""

from datetime import date, datetime

import pytest

from egregora.utils.filesystem import (
    DateExtractionError,
    FrontmatterDateFormattingError,
    _extract_clean_date,
    format_frontmatter_datetime,
)


# region: Tests for _extract_clean_date
def test_extract_clean_date_with_datetime():
    assert _extract_clean_date(datetime(2023, 1, 1, 12, 30)) == "2023-01-01"


def test_extract_clean_date_with_date():
    assert _extract_clean_date(date(2023, 1, 1)) == "2023-01-01"


def test_extract_clean_date_with_string():
    assert _extract_clean_date("2023-01-01") == "2023-01-01"


def test_extract_clean_date_with_string_and_time():
    assert _extract_clean_date("2023-01-01 12:30") == "2023-01-01"


def test_extract_clean_date_raises_on_no_date_in_string():
    with pytest.raises(DateExtractionError):
        _extract_clean_date("hello world")


def test_extract_clean_date_raises_error_on_invalid_date():
    """Verify that _extract_clean_date raises DateExtractionError for invalid dates."""
    invalid_date_str = "2023-99-99"
    with pytest.raises(DateExtractionError) as excinfo:
        _extract_clean_date(invalid_date_str)

    assert "Could not extract a valid date" in str(excinfo.value)
    assert invalid_date_str in str(excinfo.value)


# endregion


def test_format_frontmatter_datetime_raises_on_invalid_date():
    with pytest.raises(FrontmatterDateFormattingError):
        format_frontmatter_datetime("invalid-date")


# region: Coverage tests
def test_format_frontmatter_datetime_raises_on_none():
    """Verify that format_frontmatter_datetime raises an error on None input."""
    with pytest.raises(FrontmatterDateFormattingError) as excinfo:
        format_frontmatter_datetime(None)

    assert "Failed to parse date string for frontmatter: 'None'" in str(excinfo.value)


def test_extract_clean_date_raises_on_none():
    """Verify that _extract_clean_date raises an error on None input."""
    with pytest.raises(DateExtractionError) as excinfo:
        _extract_clean_date(None)
    assert "Could not extract a valid date" in str(excinfo.value)
    assert "None" in str(excinfo.value)


# endregion
