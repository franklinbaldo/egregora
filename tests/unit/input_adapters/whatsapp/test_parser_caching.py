"""Tests for WhatsApp parser caching optimization."""

from datetime import date, time

from egregora.input_adapters.whatsapp.parsing import (
    _parse_message_date,
    _parse_message_time,
)


class TestParserCaching:
    """Test that date/time parsing functions use caching effectively."""

    def test_parse_message_date_is_cached(self) -> None:
        """Verify _parse_message_date uses lru_cache."""
        # Clear any existing cache
        _parse_message_date.cache_clear()

        # Parse the same date string multiple times
        date_str = "12/25/2024"
        result1 = _parse_message_date(date_str)
        result2 = _parse_message_date(date_str)
        result3 = _parse_message_date(date_str)

        # Verify results are consistent
        assert result1 == result2 == result3
        assert result1 == date(2024, 12, 25)

        # Verify cache was hit
        cache_info = _parse_message_date.cache_info()
        assert cache_info.hits >= 2, f"Expected at least 2 cache hits, got {cache_info.hits}"
        assert cache_info.misses == 1, f"Expected 1 cache miss, got {cache_info.misses}"

    def test_parse_message_time_is_cached(self) -> None:
        """Verify _parse_message_time uses lru_cache."""
        # Clear any existing cache
        _parse_message_time.cache_clear()

        # Parse the same time string multiple times
        time_str = "10:30"
        result1 = _parse_message_time(time_str)
        result2 = _parse_message_time(time_str)
        result3 = _parse_message_time(time_str)

        # Verify results are consistent
        assert result1 == result2 == result3
        assert result1 == time(10, 30)

        # Verify cache was hit
        cache_info = _parse_message_time.cache_info()
        assert cache_info.hits >= 2, f"Expected at least 2 cache hits, got {cache_info.hits}"
        assert cache_info.misses == 1, f"Expected 1 cache miss, got {cache_info.misses}"

    def test_parse_message_time_am_pm_cached(self) -> None:
        """Verify AM/PM time parsing is also cached."""
        _parse_message_time.cache_clear()

        time_str = "2:30 PM"
        result1 = _parse_message_time(time_str)
        result2 = _parse_message_time(time_str)

        assert result1 == result2
        assert result1 == time(14, 30)

        cache_info = _parse_message_time.cache_info()
        assert cache_info.hits >= 1

    def test_different_dates_are_cached_separately(self) -> None:
        """Verify different date strings get cached separately."""
        _parse_message_date.cache_clear()

        date1 = _parse_message_date("12/25/2024")
        date2 = _parse_message_date("12/26/2024")
        date1_again = _parse_message_date("12/25/2024")

        assert date1 != date2
        assert date1 == date1_again

        cache_info = _parse_message_date.cache_info()
        assert cache_info.misses == 2  # Two unique dates
        assert cache_info.hits == 1  # One repeated lookup

    def test_cache_handles_invalid_dates(self) -> None:
        """Verify invalid dates return None and are also cached."""
        _parse_message_date.cache_clear()

        result1 = _parse_message_date("not-a-date")
        result2 = _parse_message_date("not-a-date")

        assert result1 is None
        assert result2 is None

        cache_info = _parse_message_date.cache_info()
        assert cache_info.hits == 1  # Second lookup was a cache hit
