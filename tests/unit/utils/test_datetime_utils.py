"""Tests for the refactored datetime utilities."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from freezegun import freeze_time

from egregora.utils.datetime_utils import (
    ensure_datetime,
    normalize_timezone,
    parse_datetime_flexible,
)


class MockPandasTimestamp:
    """Mock for an object with a .to_pydatetime() method (like pandas.Timestamp)."""

    def __init__(self, dt: datetime):
        self._dt = dt

    def to_pydatetime(self) -> datetime:
        return self._dt


# --- Re-implementation of original tests for TDD ---


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


@pytest.mark.parametrize(
    "input_val",
    [None, "", "   ", "not-a-date", 12345, object()],
)
def test_parse_datetime_flexible_invalid_inputs(input_val: Any):
    """Should return None for invalid, empty, or unparseable inputs."""
    assert parse_datetime_flexible(input_val) is None


def test_parse_datetime_flexible_custom_timezone():
    """Should respect a custom default timezone for naive inputs."""
    custom_tz = timezone(timedelta(hours=-5))
    naive_dt = datetime(2023, 1, 1, 12, 0, 0)

    result = parse_datetime_flexible(naive_dt, default_timezone=custom_tz)
    assert result is not None
    assert result.tzinfo == custom_tz
    assert result.hour == 12  # Time should not change, only tzinfo attached


def test_parse_datetime_flexible_forwards_parser_kwargs():
    """Should forward kwargs to the dateutil parser for string inputs."""
    raw_date = "01-02-2023"
    # dayfirst=True should parse as Feb 1st, not Jan 2nd.
    result = parse_datetime_flexible(raw_date, parser_kwargs={"dayfirst": True})
    assert result is not None
    assert result.month == 2
    assert result.day == 1


# --- Tests for normalize_timezone ---


def test_normalize_timezone_handles_naive_and_aware():
    """Should correctly normalize both naive and aware datetimes to a target timezone."""
    target_tz = timezone(timedelta(hours=-8))
    # Naive datetime
    dt_naive = datetime(2023, 1, 1, 10, 0, 0)
    # Aware datetime
    dt_aware = datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)

    # Normalize naive
    result_naive = normalize_timezone(dt_naive, default_timezone=target_tz)
    assert result_naive.tzinfo == target_tz
    assert result_naive.hour == 10  # Attach timezone

    # Normalize aware
    result_aware = normalize_timezone(dt_aware, default_timezone=target_tz)
    assert result_aware.tzinfo == target_tz
    assert result_aware.hour == 2  # Convert 10:00 UTC to UTC-8


# --- Tests for ensure_datetime ---


@freeze_time("2023-01-01 12:00:00 UTC")
def test_ensure_datetime_valid():
    """Should return a valid datetime for supported inputs."""
    assert ensure_datetime("2023-01-01") == datetime(2023, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert ensure_datetime(datetime(2023, 1, 1)) == datetime(
        2023, 1, 1, 0, 0, 0, tzinfo=UTC
    )


def test_ensure_datetime_invalid_raises_type_error():
    """Should raise TypeError for unsupported types."""
    with pytest.raises(TypeError, match="Unsupported datetime type"):
        ensure_datetime(None)
    with pytest.raises(TypeError, match="Unsupported datetime type"):
        ensure_datetime("not-a-datetime")
