from datetime import date

import pytest

from egregora.date_utils import parse_flexible_date


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("01/05/2024", date(2024, 5, 1)),
        ("5/1/2024", date(2024, 1, 5)),
        ("2024-05-01", date(2024, 5, 1)),
    ],
)
def test_parse_flexible_date_accepts_multiple_formats(
    token: str, expected: date
) -> None:
    assert parse_flexible_date(token) == expected


def test_parse_flexible_date_handles_timezones() -> None:
    token = "2024-05-01T00:30:00-03:00"
    assert parse_flexible_date(token) == date(2024, 5, 1)


def test_parse_flexible_date_without_timezone_assumption() -> None:
    token = "2024-05-01 03:00"
    assert parse_flexible_date(token, assume_tz_utc=False) == date(2024, 5, 1)


def test_parse_flexible_date_returns_none_for_blank_strings() -> None:
    assert parse_flexible_date("   ") is None


def test_parse_flexible_date_returns_none_for_invalid_tokens() -> None:
    assert parse_flexible_date("not a date") is None
