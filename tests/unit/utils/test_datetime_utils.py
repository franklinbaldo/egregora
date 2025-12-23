"""Tests for datetime utilities."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from egregora.utils.datetime_utils import parse_datetime_flexible


class MockPandasTimestamp:
    """Mock for an object with a .to_pydatetime() method (like pandas.Timestamp)."""

    def __init__(self, dt: datetime):
        self._dt = dt

    def to_pydatetime(self) -> datetime:
        return self._dt


def test_parse_datetime_none_or_empty():
    """Should return None for None or empty string inputs."""
    assert parse_datetime_flexible(None) is None
    assert parse_datetime_flexible("") is None
    assert parse_datetime_flexible("   ") is None


def test_parse_datetime_existing_datetime_naive():
    """Should return timezone-aware UTC datetime for naive datetime input."""
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = parse_datetime_flexible(dt)
    assert result is not None
    assert result.year == 2023
    assert result.tzinfo == UTC
    assert result == dt.replace(tzinfo=UTC)


def test_parse_datetime_existing_datetime_aware():
    """Should normalize aware datetime to default timezone (UTC)."""
    # Create a timezone-aware datetime (e.g., UTC+1)
    tz = timezone(timedelta(hours=1))
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=tz)

    result = parse_datetime_flexible(dt)

    assert result is not None
    assert result.tzinfo == UTC
    # 12:00 UTC+1 is 11:00 UTC
    assert result.hour == 11


def test_parse_datetime_date_object():
    """Should convert date object to datetime at midnight UTC."""
    d = date(2023, 1, 1)
    result = parse_datetime_flexible(d)

    assert result is not None
    assert isinstance(result, datetime)
    assert result.year == 2023
    assert result.hour == 0
    assert result.tzinfo == UTC


def test_parse_datetime_iso_string():
    """Should parse ISO format strings."""
    # Naive ISO string
    iso_naive = "2023-01-01T12:00:00"
    result = parse_datetime_flexible(iso_naive)
    assert result is not None
    assert result.year == 2023
    assert result.tzinfo == UTC

    # Aware ISO string
    iso_aware = "2023-01-01T12:00:00+00:00"
    result = parse_datetime_flexible(iso_aware)
    assert result is not None
    assert result.year == 2023
    assert result.tzinfo == UTC


def test_parse_datetime_fuzzy_string():
    """Should parse non-ISO strings using dateutil fallback."""
    # US format
    fuzzy = "January 1, 2023 12:00 PM"
    result = parse_datetime_flexible(fuzzy)
    assert result is not None
    assert result.year == 2023
    assert result.month == 1
    assert result.day == 1
    assert result.hour == 12
    assert result.tzinfo == UTC


def test_parse_datetime_invalid_string():
    """Should return None for unparseable strings."""
    assert parse_datetime_flexible("not a date") is None
    assert parse_datetime_flexible("!!!") is None


def test_parse_datetime_with_to_pydatetime():
    """Should handle objects with to_pydatetime method."""
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    mock_ts = MockPandasTimestamp(dt)

    result = parse_datetime_flexible(mock_ts)
    assert result == dt


def test_parse_datetime_custom_default_timezone():
    """Should respect custom default timezone."""
    custom_tz = timezone(timedelta(hours=2))
    dt_naive = datetime(2023, 1, 1, 12, 0, 0)

    result = parse_datetime_flexible(dt_naive, default_timezone=custom_tz)

    assert result is not None
    assert result.tzinfo == custom_tz
    # Should not change time, just attach timezone
    assert result.hour == 12


def test_parse_datetime_parser_kwargs():
    """Should pass kwargs to dateutil parser."""
    # "2023-01-01" could be parsed differently with dayfirst=True if ambiguous
    # Using "01-02-2023" -> Jan 2nd (default US) vs Feb 1st (dayfirst)

    raw = "01-02-2023"

    # Default (US: Month-Day-Year) -> Jan 2nd
    res_default = parse_datetime_flexible(raw)
    assert res_default.month == 1
    assert res_default.day == 2

    # Custom (Day-Month-Year) -> Feb 1st
    res_custom = parse_datetime_flexible(raw, parser_kwargs={"dayfirst": True})
    assert res_custom.month == 2
    assert res_custom.day == 1
