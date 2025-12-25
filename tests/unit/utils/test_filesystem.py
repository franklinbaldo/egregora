from datetime import date, datetime

import pytest

from egregora.utils.filesystem import _extract_clean_date


@pytest.mark.parametrize(
    ("input_date", "expected"),
    [
        # Datetime objects
        (datetime(2023, 1, 15, 10, 30), "2023-01-15"),
        (datetime(2024, 2, 29), "2024-02-29"),
        # Date objects
        (date(2023, 1, 15), "2023-01-15"),
        (date(2024, 2, 29), "2024-02-29"),
        # Valid date strings
        ("2023-01-15", "2023-01-15"),
        (" 2023-01-15 ", "2023-01-15"),
        ("2023-01-15-some-slug", "2023-01-15"),
        ("prefix-2023-01-15-suffix", "2023-01-15"),
        # Invalid date strings (should be returned as is)
        ("2023-13-01", "2023-13-01"),
        ("2023-01-32", "2023-01-32"),
        ("not-a-date", "not-a-date"),
        ("2023-99-99", "2023-99-99"),
        ("2023-02-30", "2023-02-30"),
        (" completely invalid ", "completely invalid"),
        (12345, "12345"),
    ],
)
def test_extract_clean_date(input_date, expected):
    """Test that _extract_clean_date correctly handles various inputs."""
    assert _extract_clean_date(input_date) == expected
