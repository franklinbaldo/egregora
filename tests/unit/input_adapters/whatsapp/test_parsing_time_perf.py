"""Tests for time parsing performance."""

import pytest

from egregora.input_adapters.whatsapp.parsing import _parse_message_time

# A variety of time formats to test against
TIME_FORMATS = [
    "12:30",
    "01:15",
    "23:59",
    "10:30 PM",
    "10:30 pm",
    "10:30PM",
    "1:30 AM",
    "12:00 AM",
    "12:30 AM",
    "12:00 PM",
    "12:30 PM",
    "  12:30  ",
    "9:05",
]


@pytest.mark.benchmark(
    group="parse-time",
)
@pytest.mark.parametrize("time_str", TIME_FORMATS)
def test_parse_message_time_performance(benchmark, time_str):
    """Benchmark the performance of _parse_message_time."""
    benchmark(_parse_message_time, time_str)
