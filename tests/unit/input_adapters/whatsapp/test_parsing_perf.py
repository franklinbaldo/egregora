"""Tests for parser performance improvements."""

from datetime import time

import pytest

from egregora.input_adapters.whatsapp.exceptions import TimeParsingError
from egregora.input_adapters.whatsapp.parsing import _parse_message_time


def test_parse_message_time_common_formats():
    """Verify common formats are parsed correctly."""
    assert _parse_message_time("12:30") == time(12, 30)
    assert _parse_message_time("01:15") == time(1, 15)
    assert _parse_message_time("23:59") == time(23, 59)


def test_parse_message_time_ampm():
    """Verify AM/PM parsing."""
    assert _parse_message_time("10:30 PM") == time(22, 30)
    assert _parse_message_time("10:30 pm") == time(22, 30)
    assert _parse_message_time("10:30PM") == time(22, 30)

    assert _parse_message_time("1:30 AM") == time(1, 30)
    assert _parse_message_time("12:00 AM") == time(0, 0)
    assert _parse_message_time("12:30 AM") == time(0, 30)
    assert _parse_message_time("12:00 PM") == time(12, 0)
    assert _parse_message_time("12:30 PM") == time(12, 30)


def test_parse_message_time_variations():
    """Verify variations in whitespace and formatting."""
    assert _parse_message_time("  12:30  ") == time(12, 30)
    assert _parse_message_time("9:05") == time(9, 5)


def test_parse_message_time_invalid():
    """Verify invalid inputs raise TimeParsingError."""
    with pytest.raises(TimeParsingError):
        _parse_message_time("")
    with pytest.raises(TimeParsingError):
        _parse_message_time("invalid")
    with pytest.raises(TimeParsingError):
        _parse_message_time("12:60")  # Invalid minute
    with pytest.raises(TimeParsingError):
        _parse_message_time("25:00")  # Invalid hour
    with pytest.raises(TimeParsingError):
        _parse_message_time("10:30 XM")  # Invalid suffix
