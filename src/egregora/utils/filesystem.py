"""Filesystem utilities for writing structured content.

This module consolidates file writing logic previously scattered across adapters.
It provides standard helpers for:
- Writing markdown posts with frontmatter
- Handling safe filenames and collision resolution
- Managing directory structures
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime

from egregora.utils.datetime_utils import (
    DateTimeParsingError,
    InvalidDateTimeInputError,
    parse_datetime_flexible,
)

logger = logging.getLogger(__name__)

ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)
_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _extract_clean_date(date_obj: str | date | datetime) -> str:
    """Extract a clean ``YYYY-MM-DD`` date from user-provided input."""
    if isinstance(date_obj, datetime):
        return date_obj.date().isoformat()
    if isinstance(date_obj, date):
        return date_obj.isoformat()

    date_str = str(date_obj).strip()

    # Fallback to regex for strings to find dates within larger text bodies.
    match = _DATE_PATTERN.search(date_str)
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
        dt = parse_datetime_flexible(raw_date, default_timezone=UTC)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (DateTimeParsingError, AttributeError, ValueError, InvalidDateTimeInputError) as e:
        # This will be raised if parse_datetime_flexible fails,
        # which covers all failure modes (None input, empty strings, bad data).
        raise FrontmatterDateFormattingError(str(raw_date), e) from e


class FilesystemError(Exception):
    """Base exception for filesystem-related errors."""


class MissingMetadataError(FilesystemError):
    """Raised when required metadata for a post is missing."""

    def __init__(self, missing_keys: list[str]) -> None:
        self.missing_keys = missing_keys
        message = f"Missing required metadata keys: {', '.join(missing_keys)}"
        super().__init__(message)


class UniqueFilenameError(FilesystemError):
    """Raised when a unique filename cannot be generated after a set number of attempts."""

    def __init__(self, base_slug: str, attempts: int) -> None:
        self.base_slug = base_slug
        self.attempts = attempts
        message = f"Could not generate a unique filename for slug '{base_slug}' after {attempts} attempts."
        super().__init__(message)


class FrontmatterDateFormattingError(FilesystemError):
    """Raised when a date string for frontmatter cannot be parsed."""

    def __init__(self, date_str: str, original_exception: Exception) -> None:
        self.date_str = date_str
        self.original_exception = original_exception
        super().__init__(
            f"Failed to parse date string for frontmatter: '{self.date_str}'. "
            f"Original error: {original_exception}"
        )


class FilesystemOperationError(FilesystemError):
    """Base exception for file I/O errors."""

    def __init__(self, path: str, original_exception: Exception, message: str | None = None) -> None:
        self.path = path
        self.original_exception = original_exception
        if message is None:
            message = f"An error occurred at path: {self.path}. Original error: {original_exception}"
        super().__init__(message)


class DirectoryCreationError(FilesystemOperationError):
    """Raised when creating a directory fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to create directory at: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class FileWriteError(FilesystemOperationError):
    """Raised when writing a file fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to write file to: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class DateExtractionError(FilesystemError):
    """Raised when a date cannot be extracted from a string."""

    def __init__(self, date_str: str, original_exception: Exception | None = None) -> None:
        self.date_str = date_str
        self.original_exception = original_exception
        message = f"Could not extract a valid date from '{self.date_str}'"
        if original_exception:
            message += f". Original error: {original_exception}"
        super().__init__(message)
