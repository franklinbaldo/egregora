"""Date and time utilities."""

from __future__ import annotations

from datetime import UTC, date, datetime, tzinfo
from typing import TYPE_CHECKING, Any

from dateutil import parser as dateutil_parser

if TYPE_CHECKING:
    from collections.abc import Mapping


def parse_datetime_flexible(
    value: datetime | date | str | Any | None,
    *,
    default_timezone: tzinfo = UTC,
    parser_kwargs: Mapping[str, Any] | None = None,
) -> datetime | None:
    """Parse a datetime-like value from various formats into a timezone-aware object.

    This function handles ``datetime``, ``date``, strings, and objects with a
    ``.to_pydatetime()`` method. It ensures the returned datetime is always
    timezone-aware.

    - If the input is already a ``datetime`` with a timezone, it's normalized to the
      ``default_timezone``.
    - If the input is a naive ``datetime`` or ``date``, it's made aware using the
      ``default_timezone``.
    - If the input is a string, it's parsed, and if naive, made aware using the
      ``default_timezone``.

    Args:
        value: The datetime-like value to parse. Returns ``None`` if the input is
            ``None``, an empty string, or cannot be parsed.
        default_timezone: The timezone to apply to naive datetimes. Defaults to UTC.
        parser_kwargs: Additional keyword arguments for ``dateutil.parser.parse``
            when parsing string inputs.

    Returns:
        A timezone-aware ``datetime`` object normalized to the ``default_timezone``,
        or ``None`` if parsing is unsuccessful.

    """
    if value is None:
        return None

    # Handle objects with a .to_pydatetime() method (e.g., pandas Timestamps)
    if hasattr(value, "to_pydatetime") and callable(value.to_pydatetime):
        value = value.to_pydatetime()

    dt = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str):
        stripped_value = value.strip()
        if not stripped_value:
            return None
        try:
            dt = dateutil_parser.parse(stripped_value, **(parser_kwargs or {}))
        except (ValueError, TypeError, OverflowError):
            return None
    else:
        return None

    return normalize_timezone(dt, default_timezone=default_timezone)


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
    """Parse a value into a timezone-aware datetime, raising TypeError on failure.

    This serves as a strict version of ``parse_datetime_flexible``, suitable for
    cases where a valid datetime is required.

    Args:
        value: The value to convert.

    Returns:
        A timezone-aware ``datetime`` object.

    Raises:
        TypeError: If the value cannot be converted to a ``datetime``.

    """
    parsed = parse_datetime_flexible(value, default_timezone=UTC)
    if parsed is not None:
        return parsed

    msg = f"Unsupported datetime type: {type(value)}"
    raise TypeError(msg)


__all__ = ["ensure_datetime", "normalize_timezone", "parse_datetime_flexible"]
