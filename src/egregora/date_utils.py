"""Utility helpers for parsing WhatsApp date strings."""

from datetime import date, timezone
from typing import Iterable

from dateutil import parser as date_parser


_DATE_PARSE_PREFERENCES: tuple[dict[str, bool], ...] = (
    {"dayfirst": True},
    {"dayfirst": False},
)


def parse_flexible_date(token: str, *, assume_tz_utc: bool = True) -> date | None:
    """Parse WhatsApp date tokens handling mixed locales and formats."""

    normalized = token.strip()
    if not normalized:
        return None

    tzinfo = timezone.utc if assume_tz_utc else None
    preferences: Iterable[dict[str, bool]] = _DATE_PARSE_PREFERENCES

    for options in preferences:
        try:
            parsed = date_parser.parse(normalized, **options)
        except (ValueError, OverflowError, TypeError):
            continue

        if parsed.tzinfo is None and tzinfo is not None:
            parsed = parsed.replace(tzinfo=tzinfo)
        elif tzinfo is not None:
            parsed = parsed.astimezone(tzinfo)

        return parsed.date()

    return None
