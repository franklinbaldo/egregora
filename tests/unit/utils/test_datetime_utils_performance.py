from datetime import UTC, date, datetime

import pytest

from egregora.utils.datetime_utils import (
    DateTimeParsingError,
    InvalidDateTimeInputError,
    parse_datetime_flexible,
)


# Test cases for correctness
@pytest.mark.parametrize(
    ("input_val", "expected_type"),
    [
        (datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC), datetime),
        (date(2025, 1, 1), datetime),
        ("2025-01-01T12:00:00Z", datetime),
        ("2025-01-01 12:00:00", datetime),
        ("01/01/2025", datetime),
    ],
)
def test_parse_datetime_flexible_correctness(input_val, expected_type):
    """Verify parse_datetime_flexible returns the correct type."""
    result = parse_datetime_flexible(input_val)
    assert isinstance(result, expected_type)
    assert result.tzinfo is not None


@pytest.mark.parametrize(
    ("invalid_input", "expected_exception"),
    [
        (None, InvalidDateTimeInputError),
        ("", InvalidDateTimeInputError),
        (" ", InvalidDateTimeInputError),
        ("not a date", DateTimeParsingError),
        (object(), DateTimeParsingError),
    ],
)
def test_parse_datetime_flexible_exceptions(invalid_input, expected_exception):
    """Verify parse_datetime_flexible raises exceptions for invalid inputs."""
    with pytest.raises(expected_exception):
        parse_datetime_flexible(invalid_input)


# Test cases for benchmark
@pytest.mark.parametrize(
    "input_val",
    [
        datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        "2025-01-01T12:00:00Z",
        "Jan 1, 2025 12:00 PM",
    ],
)
def test_parse_datetime_flexible_benchmark(benchmark, input_val):
    """Benchmark the parse_datetime_flexible function."""
    benchmark(parse_datetime_flexible, input_val)
