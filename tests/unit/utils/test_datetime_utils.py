"""Tests for datetime utilities."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from egregora.utils.datetime_utils import (
    _to_datetime,
    normalize_timezone,
    parse_datetime_flexible,
)


# region: Tests for normalize_timezone
def test_normalize_timezone_naive_datetime():
    """Should make a naive datetime aware in the default timezone (UTC)."""
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = normalize_timezone(dt)
    assert result.tzinfo == UTC
    assert result.hour == 12  # Time should not change, only tzinfo attached


def test_normalize_timezone_aware_datetime():
    """Should convert an aware datetime to the default timezone (UTC)."""
    tz = timezone(timedelta(hours=2))
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=tz)
    result = normalize_timezone(dt)
    assert result.tzinfo == UTC
    assert result.hour == 10  # 12:00 UTC+2 is 10:00 UTC


def test_normalize_timezone_already_in_default_timezone():
    """Should not change a datetime that is already in the default timezone."""
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = normalize_timezone(dt)
    assert result == dt
    assert result.tzinfo == UTC


def test_normalize_timezone_custom_default_timezone():
    """Should respect a custom default timezone."""
    custom_tz = timezone(timedelta(hours=-5))

    # Test with naive datetime
    dt_naive = datetime(2023, 1, 1, 12, 0, 0)
    result_naive = normalize_timezone(dt_naive, default_timezone=custom_tz)
    assert result_naive.tzinfo == custom_tz
    assert result_naive.hour == 12

    # Test with aware datetime
    dt_aware = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    result_aware = normalize_timezone(dt_aware, default_timezone=custom_tz)
    assert result_aware.tzinfo == custom_tz
    assert result_aware.hour == 7  # 12:00 UTC is 7:00 UTC-5


# endregion


# region: Tests for _to_datetime
class MockPandasTimestamp:
    """Mock for an object with a .to_pydatetime() method (like pandas.Timestamp)."""

    def __init__(self, dt: datetime):
        self._dt = dt

    def to_pydatetime(self) -> datetime:
        return self._dt


@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        (datetime(2023, 1, 1, 10, 0, 0), datetime(2023, 1, 1, 10, 0, 0)),
        (date(2023, 1, 1), datetime(2023, 1, 1, 0, 0, 0)),
        ("2023-01-01T10:00:00", datetime(2023, 1, 1, 10, 0, 0)),
        (
            MockPandasTimestamp(datetime(2023, 1, 1, 10, 0, 0)),
            datetime(2023, 1, 1, 10, 0, 0),
        ),
    ],
)
def test_to_datetime_valid_inputs(input_val, expected):
    """Should convert various valid input types to a datetime object."""
    assert _to_datetime(input_val) == expected


from egregora.utils.exceptions import DateTimeParsingError


@pytest.mark.parametrize(
    "input_val",
    [None, "", "   ", "not-a-date", 12345, "2023-99-99"],
)
def test_to_datetime_invalid_inputs_raise_exception(input_val):
    """Should raise DateTimeParsingError for invalid or empty inputs."""
    with pytest.raises(DateTimeParsingError):
        _to_datetime(input_val)


def test_to_datetime_forwards_parser_kwargs():
    """Should forward kwargs to the dateutil parser."""
    raw = "01-02-2023"
    # dayfirst=True should parse as Feb 1st, not Jan 2nd.
    result = _to_datetime(raw, parser_kwargs={"dayfirst": True})
    assert result is not None
    assert result.month == 2
    assert result.day == 1


# endregion


# region: Original tests for parse_datetime_flexible to ensure no regressions
@pytest.mark.parametrize(
    "invalid_input",
    [None, "", "   ", "not a date", "!!!", "2023-99-99"],
)
def test_parse_datetime_flexible_invalid_inputs_raise_exception(invalid_input):
    """Should raise DateTimeParsingError for invalid, None, or empty string inputs."""
    with pytest.raises(DateTimeParsingError):
        parse_datetime_flexible(invalid_input)


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
    assert res_default is not None
    assert res_default.month == 1
    assert res_default.day == 2

    # Custom (Day-Month-Year) -> Feb 1st
    res_custom = parse_datetime_flexible(raw, parser_kwargs={"dayfirst": True})
    assert res_custom is not None
    assert res_custom.month == 2
    assert res_custom.day == 1


# endregion
