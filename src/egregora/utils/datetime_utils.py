"""Date and time utilities."""

from __future__ import annotations

from datetime import UTC, date, datetime, tzinfo
from typing import TYPE_CHECKING, Any

from dateutil import parser as dateutil_parser

from egregora.utils.exceptions import (
    DateTimeParsingError,
    InvalidDateTimeInputError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


def parse_datetime_flexible(
    value: datetime | date | str | Any | None,
    *,
    default_timezone: tzinfo = UTC,
    parser_kwargs: Mapping[str, Any] | None = None,
) -> datetime:
    """Parse a datetime value using a flexible approach.

    Args:
        value: Datetime-like input (datetime/date/str/other). ``None`` or empty strings
            will raise an exception.
        default_timezone: Timezone assigned to naive datetimes and used for
            normalization when a timezone is present.
        parser_kwargs: Additional keyword arguments forwarded to ``dateutil.parser``.

    Returns:
        A timezone-normalized ``datetime``.

    Raises:
        InvalidDateTimeInputError: if the input is None or an empty string.
        DateTimeParsingError: if parsing fails.
    """
    dt = _to_datetime(value, parser_kwargs=parser_kwargs)
    return normalize_timezone(dt, default_timezone=default_timezone)


def _to_datetime(value: Any, *, parser_kwargs: Mapping[str, Any] | None = None) -> datetime:
    """Convert a value to a datetime object without timezone normalization."""
    if value is None:
        raise InvalidDateTimeInputError("None", "Input value cannot be None")

    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()

    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    raw = str(value).strip()
    if not raw:
        raise InvalidDateTimeInputError(
            str(value), "Input value cannot be an empty or whitespace-only string"
        )

    try:
        return dateutil_parser.parse(raw, **(parser_kwargs or {}))
    except (TypeError, ValueError, OverflowError) as e:
        raise DateTimeParsingError(raw, e) from e


def normalize_timezone(dt: datetime, *, default_timezone: tzinfo = UTC) -> datetime:
    """Normalize a datetime to a specific timezone.

    - If the datetime is naive, it's made aware in the `default_timezone`.
    - If the datetime is aware, it's converted to the `default_timezone`.

    Args:
        dt: The datetime to normalize.
        default_timezone: The target timezone.

    Returns:
        A timezone-aware datetime.

    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=default_timezone)
    return dt.astimezone(default_timezone)


def ensure_datetime(value: datetime | str | Any) -> datetime:
    """Convert various datetime representations to Python datetime."""
    try:
        return parse_datetime_flexible(value, default_timezone=UTC)
    except (DateTimeParsingError, InvalidDateTimeInputError) as e:
        msg = f"Unsupported datetime type: {type(value)}"
        raise TypeError(msg) from e


__all__ = ["ensure_datetime", "normalize_timezone", "parse_datetime_flexible"]
