"""Performance tests for datetime utilities."""

import pytest

from egregora.data_primitives.datetime_utils import parse_datetime_flexible

# A variety of date formats to test against
DATE_FORMATS = [
    "2025-01-01",
    "2025-01-01T12:00:00",
    "2025-01-01 12:00:00",
    "01/01/2025",
    "Jan 1, 2025",
    "Wednesday, January 1, 2025",
]


@pytest.mark.benchmark(
    group="parse-datetime",
)
@pytest.mark.parametrize("date_str", DATE_FORMATS)
def test_parse_datetime_flexible_performance(benchmark, date_str):
    """Benchmark the performance of parse_datetime_flexible."""
    benchmark(parse_datetime_flexible, date_str)
