"""Tests for the refactored datetime utilities."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from freezegun import freeze_time

from egregora.utils.datetime_utils import (
    _to_datetime,
    ensure_datetime,
    normalize_timezone,
    parse_datetime_flexible,
)
from egregora.utils.exceptions import (
    DateTimeParsingError,
    InvalidDateTimeInputError,
)


class MockPandasTimestamp:
    """Mock for an object with a .to_pydatetime() method (like pandas.Timestamp)."""

    def __init__(self, dt: datetime):
        self._dt = dt

    def to_pydatetime(self) -> datetime:
        return self._dt


# region: Tests for normalize_timezone
def test_normalize_timezone_naive_datetime():
    """Should make a naive datetime aware in the default timezone (UTC)."""
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = normalize_timezone(dt)
    assert result.tzinfo == UTC
    assert result.hour == 12


def test_normalize_timezone_aware_datetime():
    """Should convert an aware datetime to the default timezone (UTC)."""
    tz = timezone(timedelta(hours=2))
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=tz)
    result = normalize_timezone(dt)
    assert result.tzinfo == UTC
    assert result.hour == 10


def test_normalize_timezone_already_in_default_timezone():
    """Should not change a datetime that is already in the default timezone."""
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = normalize_timezone(dt)
    assert result == dt
    assert result.tzinfo == UTC


def test_normalize_timezone_custom_default_timezone():
    """Should respect a custom default timezone."""
    custom_tz = timezone(timedelta(hours=-5))
    dt_naive = datetime(2023, 1, 1, 12, 0, 0)
    result_naive = normalize_timezone(dt_naive, default_timezone=custom_tz)
    assert result_naive.tzinfo == custom_tz
    assert result_naive.hour == 12

    dt_aware = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    result_aware = normalize_timezone(dt_aware, default_timezone=custom_tz)
    assert result_aware.tzinfo == custom_tz
    assert result_aware.hour == 7


# endregion


# region: Tests for _to_datetime
@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        (datetime(2023, 1, 1, 10, 0, 0), datetime(2023, 1, 1, 10, 0, 0)),
        (date(2023, 1, 1), datetime(2023, 1, 1, 0, 0, 0)),
        ("2023-01-01T10:00:00", datetime(2023, 1, 1, 10, 0, 0)),
        (
            MockPandasTimestamp(datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)),
            datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
    ],
)
def test_to_datetime_valid_inputs(input_val, expected):
    """Should convert various valid input types to a datetime object."""
    assert _to_datetime(input_val) == expected


@pytest.mark.parametrize("input_val", [None, "", "   "])
def test_to_datetime_empty_inputs_raise_invalid_error(input_val):
    """Should raise InvalidDateTimeInputError for None or empty/whitespace strings."""
    with pytest.raises(InvalidDateTimeInputError):
        _to_datetime(input_val)


@pytest.mark.parametrize("input_val", ["not-a-date", 12345])
def test_to_datetime_unparseable_inputs_raise_parsing_error(input_val):
    """Should raise DateTimeParsingError for values that are not parsable as dates."""
    with pytest.raises(DateTimeParsingError):
        _to_datetime(input_val)


def test_to_datetime_forwards_parser_kwargs():
    """Should forward kwargs to the dateutil parser."""
    raw = "01-02-2023"
    result = _to_datetime(raw, parser_kwargs={"dayfirst": True})
    assert result is not None
    assert result.month == 2
    assert result.day == 1


# endregion


# region: Tests for parse_datetime_flexible
@pytest.mark.parametrize(
    ("input_val", "expected_hour_utc"),
    [
        (datetime(2023, 1, 1, 12, 0, 0), 12),
        (datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2))), 10),
        (datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC), 12),
        (date(2023, 1, 1), 0),
        ("2023-01-01T12:00:00", 12),
        ("2023-01-01T12:00:00Z", 12),
        ("January 1, 2023 12:00 PM", 12),
        (MockPandasTimestamp(datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)), 12),
    ],
)
def test_parse_datetime_flexible_valid_inputs(input_val: Any, expected_hour_utc: int):
    """Should correctly parse various valid inputs and normalize to UTC."""
    result = parse_datetime_flexible(input_val)
    assert result is not None
    assert result.tzinfo == UTC
    assert result.year == 2023
    assert result.month == 1
    assert result.day == 1
    assert result.hour == expected_hour_utc


@pytest.mark.parametrize("input_val", [None, "", "   "])
def test_parse_datetime_flexible_empty_inputs_raise_invalid_error(input_val: Any):
    """Should raise InvalidDateTimeInputError for invalid or empty inputs."""
    with pytest.raises(InvalidDateTimeInputError):
        parse_datetime_flexible(input_val)


@pytest.mark.parametrize("input_val", ["not-a-date", 12345, object()])
def test_parse_datetime_flexible_unparseable_inputs_raise_parsing_error(input_val: Any):
    """Should raise DateTimeParsingError for unparseable inputs."""
    with pytest.raises(DateTimeParsingError):
        parse_datetime_flexible(input_val)


def test_parse_datetime_flexible_custom_timezone():
    """Should respect a custom default timezone for naive inputs."""
    custom_tz = timezone(timedelta(hours=-5))
    naive_dt = datetime(2023, 1, 1, 12, 0, 0)

    result = parse_datetime_flexible(naive_dt, default_timezone=custom_tz)
    assert result is not None
    assert result.tzinfo == custom_tz
    assert result.hour == 12


def test_parse_datetime_flexible_forwards_parser_kwargs():
    """Should forward kwargs to the dateutil parser for string inputs."""
    raw_date = "01-02-2023"
    result = parse_datetime_flexible(raw_date, parser_kwargs={"dayfirst": True})
    assert result is not None
    assert result.month == 2
    assert result.day == 1


def test_parse_datetime_existing_datetime_naive():
    """Should return timezone-aware UTC datetime for naive datetime input."""
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = parse_datetime_flexible(dt)
    assert result.year == 2023
    assert result.tzinfo == UTC
    assert result == dt.replace(tzinfo=UTC)


def test_parse_datetime_existing_datetime_aware():
    """Should normalize aware datetime to default timezone (UTC)."""
    tz = timezone(timedelta(hours=1))
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=tz)

    result = parse_datetime_flexible(dt)

    assert result.tzinfo == UTC
    assert result.hour == 11


def test_parse_datetime_date_object():
    """Should convert date object to datetime at midnight UTC."""
    d = date(2023, 1, 1)
    result = parse_datetime_flexible(d)

    assert isinstance(result, datetime)
    assert result.year == 2023
    assert result.hour == 0
    assert result.tzinfo == UTC


def test_parse_datetime_iso_string():
    """Should parse ISO format strings."""
    iso_naive = "2023-01-01T12:00:00"
    result = parse_datetime_flexible(iso_naive)
    assert result.year == 2023
    assert result.tzinfo == UTC

    iso_aware = "2023-01-01T12:00:00+00:00"
    result = parse_datetime_flexible(iso_aware)
    assert result.year == 2023
    assert result.tzinfo == UTC


def test_parse_datetime_fuzzy_string():
    """Should parse non-ISO strings using dateutil fallback."""
    fuzzy = "January 1, 2023 12:00 PM"
    result = parse_datetime_flexible(fuzzy)
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

    assert result.tzinfo == custom_tz
    assert result.hour == 12


def test_parse_datetime_parser_kwargs():
    """Should pass kwargs to dateutil parser."""
    raw = "01-02-2023"
    res_default = parse_datetime_flexible(raw)
    assert res_default.month == 1
    assert res_default.day == 2

    res_custom = parse_datetime_flexible(raw, parser_kwargs={"dayfirst": True})
    assert res_custom.month == 2
    assert res_custom.day == 1


# endregion


# region: Tests for ensure_datetime
@freeze_time("2023-01-01 12:00:00 UTC")
def test_ensure_datetime_valid():
    """Should return a valid datetime for supported inputs."""
    assert ensure_datetime("2023-01-01") == datetime(2023, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert ensure_datetime(datetime(2023, 1, 1)) == datetime(2023, 1, 1, 0, 0, 0, tzinfo=UTC)


def test_ensure_datetime_invalid_raises_type_error():
    """Should raise TypeError for unsupported types."""
    with pytest.raises(TypeError, match="Unsupported datetime type"):
        ensure_datetime(None)
    with pytest.raises(TypeError, match="Unsupported datetime type"):
        ensure_datetime("not-a-datetime")


# endregion
