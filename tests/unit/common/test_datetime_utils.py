"""Unit tests for datetime utilities."""

from datetime import UTC, date, datetime

import pytest
from freezegun import freeze_time

from egregora.common.datetime_utils import (
    DateTimeParsingError,
    InvalidDateTimeInputError,
    parse_datetime_flexible,
)

# Define a set of valid inputs and their expected outputs
VALID_INPUTS = {
    "iso_date": ("2025-01-01", datetime(2025, 1, 1, tzinfo=UTC)),
    "iso_datetime": ("2025-01-01T12:00:00", datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)),
    "iso_datetime_zulu": ("2025-01-01T12:00:00Z", datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)),
    "human_date": ("Jan 1, 2025", datetime(2025, 1, 1, tzinfo=UTC)),
    "datetime_obj": (datetime(2025, 1, 1, 12, 0, 0), datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)),
    "date_obj": (date(2025, 1, 1), datetime(2025, 1, 1, tzinfo=UTC)),
    "time_only": (
        "12:00:00",
        datetime.combine(date(2025, 1, 1), datetime.min.time().replace(hour=12), tzinfo=UTC),
    ),
    "us_date_slashes": ("01/01/2025", datetime(2025, 1, 1, tzinfo=UTC)),
    "ambiguous_us_date": ("01/02/2025", datetime(2025, 1, 2, tzinfo=UTC)),  # MDY preferred
    "international_date": ("13/01/2025", datetime(2025, 1, 13, tzinfo=UTC)),
    "long_date": ("Wednesday, January 1, 2025", datetime(2025, 1, 1, tzinfo=UTC)),
}

# Define a set of invalid inputs and the exceptions they should raise
INVALID_INPUTS = {
    "none": (None, InvalidDateTimeInputError),
    "empty_string": ("", InvalidDateTimeInputError),
    "whitespace": ("   ", InvalidDateTimeInputError),
    "invalid_string": ("not a date", DateTimeParsingError),
    "integer": (123, DateTimeParsingError),
}


@pytest.mark.parametrize(("input_val", "expected"), VALID_INPUTS.values(), ids=VALID_INPUTS.keys())
@freeze_time("2025-01-01")
def test_parse_datetime_flexible_correctness(input_val, expected):
    """Verify that parse_datetime_flexible correctly parses valid inputs."""
    assert parse_datetime_flexible(input_val) == expected


@pytest.mark.parametrize(("input_val", "exception"), INVALID_INPUTS.values(), ids=INVALID_INPUTS.keys())
def test_parse_datetime_flexible_exceptions(input_val, exception):
    """Verify that parse_datetime_flexible raises the correct exceptions for invalid inputs."""
    with pytest.raises(exception):
        parse_datetime_flexible(input_val)


def test_parse_datetime_flexible_parser_kwargs():
    """Verify that parser_kwargs are respected and bypass the fast path."""
    # 01/02/2025 should be parsed as Feb 1st (DMY) when dayfirst=True
    # The default/fast path would parse it as Jan 2nd (MDY)
    result = parse_datetime_flexible("01/02/2025", parser_kwargs={"dayfirst": True})
    assert result == datetime(2025, 2, 1, tzinfo=UTC)
