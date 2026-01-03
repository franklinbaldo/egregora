# tests/unit/utils/test_filesystem_performance.py
import datetime

import pytest
from freezegun import freeze_time

from egregora.utils.filesystem import DateExtractionError, _extract_clean_date

# Valid date inputs that should be successfully extracted
VALID_DATE_TEST_CASES = [
    ("2025-01-15", "2025-01-15"),
    ("  2025-01-15  ", "2025-01-15"),
    (datetime.date(2025, 1, 15), "2025-01-15"),
    (datetime.datetime(2025, 1, 15, 10, 30), "2025-01-15"),
    ("Some event on 2025-01-15", "2025-01-15"),
]

# Invalid date inputs that should raise DateExtractionError
INVALID_DATE_TEST_CASES = [
    "2025-99-99 is not a date",
    "No date here",
    None,
]


@pytest.mark.parametrize(("input_val", "expected"), VALID_DATE_TEST_CASES)
def test_extract_clean_date_benchmark(benchmark, input_val, expected):
    """Benchmark the performance of the original _extract_clean_date function."""
    # This test serves a dual purpose:
    # 1. Verifies the correctness of the function's output.
    # 2. Establishes a performance baseline before optimization.

    # We freeze time to ensure that tests involving `datetime.now()` are deterministic,
    # though none of the current test cases rely on it directly. It's good practice.
    with freeze_time("2025-01-15"):
        # The benchmark fixture runs the function multiple times to get a reliable timing.
        result = benchmark(_extract_clean_date, input_val)

        # We assert correctness on the *last* run's result provided by the fixture.
        assert result == expected


@pytest.mark.parametrize("input_val", INVALID_DATE_TEST_CASES)
def test_extract_clean_date_invalid_inputs(input_val):
    """Test that invalid date inputs raise DateExtractionError."""
    with freeze_time("2025-01-15"):
        with pytest.raises(DateExtractionError):
            _extract_clean_date(input_val)
