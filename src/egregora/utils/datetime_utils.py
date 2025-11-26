"""Date and time utilities."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Mapping

from dateutil import parser as dateutil_parser


def parse_datetime_flexible(
    value: datetime | date | str | Any | None,
    *,
    default_timezone=UTC,
    parser_kwargs: Mapping[str, Any] | None = None,
) -> datetime | None:
    """Parse a datetime value with ISO-first logic and optional dateutil fallback.

    Args:
        value: Datetime-like input (datetime/date/str/other). ``None`` or empty strings
            return ``None``.
        default_timezone: Timezone assigned to naive datetimes and used for
            normalization when a timezone is present.
        parser_kwargs: Additional keyword arguments forwarded to ``dateutil.parser``.

    Returns:
        A timezone-normalized ``datetime`` or ``None`` if parsing fails.
    """

    if value is None:
        return None

    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
    else:
        raw = str(value).strip()
        if not raw:
            return None

        try:
            dt = datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            kwargs = dict(parser_kwargs or {})
            try:
                dt = dateutil_parser.parse(raw, **kwargs)
            except (TypeError, ValueError, OverflowError):
                return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_timezone)
    else:
        dt = dt.astimezone(default_timezone)

    return dt


__all__ = ["parse_datetime_flexible"]
