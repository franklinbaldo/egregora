import pytest
from datetime import datetime, timezone

from egregora_v3.engine.filters import format_datetime


@pytest.mark.parametrize(
    ("dt", "format_str", "expected"),
    [
        (
            datetime(2025, 12, 25, 10, 30, 0, tzinfo=timezone.utc),
            "%Y-%m-%d %H:%M:%S",
            "2025-12-25 10:30:00",
        ),
        (
            datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "%Y/%m/%d",
            "2025/01/01",
        ),
        (
            datetime(2024, 7, 4, 15, 0, 0, tzinfo=timezone.utc),
            "%A, %B %d, %Y",
            "Thursday, July 04, 2024",
        ),
    ],
)
def test_format_datetime_with_valid_datetimes(
    dt: datetime, format_str: str, expected: str
):
    """Verify format_datetime formats datetimes with different format strings."""
    assert format_datetime(dt, format_str) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("not a datetime", "not a datetime"),
        (None, "None"),
        (123, "123"),
    ],
)
def test_format_datetime_with_invalid_inputs(value: any, expected: str):
    """Verify format_datetime handles non-datetime inputs gracefully."""
    assert format_datetime(value) == expected
