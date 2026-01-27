"""Date and time utilities for markdown files."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from egregora.data_primitives.datetime_utils import (
    DateTimeError,
    DateTimeParsingError,
    InvalidDateTimeInputError,
    parse_datetime_flexible,
)

DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def extract_clean_date(date_obj: str | date | datetime) -> str:
    """Extract a clean ``YYYY-MM-DD`` date from user-provided input."""
    if isinstance(date_obj, datetime):
        return date_obj.date().isoformat()
    if isinstance(date_obj, date):
        return date_obj.isoformat()

    date_str = str(date_obj).strip()

    # Fallback to regex for strings to find dates within larger text bodies.
    match = DATE_PATTERN.search(date_str)
    if not match:
        raise DateExtractionError(date_str)

    try:
        # Use our robust parser on the *matched part* of the string.
        parsed_dt = parse_datetime_flexible(match.group(1))
        return parsed_dt.date().isoformat()
    except (DateTimeParsingError, InvalidDateTimeInputError) as e:
        # The pattern was not a valid date (e.g., "2023-99-99"), so fallback.
        raise DateExtractionError(date_str, e) from e


def format_frontmatter_datetime(raw_date: str | date | datetime) -> str:
    """Normalize a metadata date into the RSS-friendly ``YYYY-MM-DD HH:MM`` string."""
    try:
        # Pre-process string inputs to handle ranges like "2025-01-01 10:00 to 11:00"
        if isinstance(raw_date, str) and " to " in raw_date:
            raw_date = raw_date.split(" to ")[0].strip()

        dt = parse_datetime_flexible(raw_date, default_timezone=UTC)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (DateTimeParsingError, AttributeError, ValueError, InvalidDateTimeInputError) as e:
        # This will be raised if parse_datetime_flexible fails,
        # which covers all failure modes (None input, empty strings, bad data).
        raise FrontmatterDateFormattingError(str(raw_date), e) from e


class FrontmatterDateFormattingError(DateTimeError):
    """Raised when a date string for frontmatter cannot be parsed."""

    def __init__(self, date_str: str, original_exception: Exception) -> None:
        self.date_str = date_str
        self.original_exception = original_exception
        super().__init__(
            f"Failed to parse date string for frontmatter: '{self.date_str}'. "
            f"Original error: {original_exception}"
        )


class DateExtractionError(DateTimeError):
    """Raised when a date cannot be extracted from a string."""

    def __init__(self, date_str: str, original_exception: Exception | None = None) -> None:
        self.date_str = date_str
        self.original_exception = original_exception
        message = f"Could not extract a valid date from '{self.date_str}'"
        if original_exception:
            message += f". Original error: {original_exception}"
        super().__init__(message)


__all__ = [
    "DateExtractionError",
    "FrontmatterDateFormattingError",
    "extract_clean_date",
    "format_frontmatter_datetime",
]
