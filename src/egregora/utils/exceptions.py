"""Compatibility exceptions for legacy imports."""

from egregora.utils.datetime_utils import (  # noqa: F401
    DateTimeError,
    DateTimeParsingError,
    InvalidDateTimeInputError,
)

__all__ = [
    "DateTimeError",
    "DateTimeParsingError",
    "InvalidDateTimeInputError",
]
