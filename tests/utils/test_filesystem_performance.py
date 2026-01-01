"""Filesystem performance tests."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from egregora.utils.datetime_utils import extract_clean_date

VALID_DATE_INPUTS = [
    ("2023-01-15", "2023-01-15"),
    (date(2023, 1, 15), "2023-01-15"),
    (datetime(2023, 1, 15, 10, 30), "2023-01-15"),
    ("  2023-01-15T10:30:00Z  ", "2023-01-15"),
    ("Some text surrounding 2023-01-15 and other things", "2023-01-15"),
]


@pytest.mark.benchmark(group="extract-clean-date")
@pytest.mark.parametrize(("input_date", "expected"), VALID_DATE_INPUTS)
def test_extract_clean_date_benchmark(benchmark, input_date, expected):
    """Benchmark the extract_clean_date function."""
    result = benchmark(extract_clean_date, input_date)
    assert result == expected
