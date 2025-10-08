"""Utility helpers for parsing WhatsApp date strings."""

from collections.abc import Iterable
from datetime import UTC, date, datetime

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

    tzinfo = UTC if assume_tz_utc else None

    def _normalize(parsed: datetime) -> date:
        if tzinfo is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=tzinfo)
            else:
                parsed = parsed.astimezone(tzinfo)
        return parsed.date()

    try:
        parsed_iso = date_parser.isoparse(normalized)
    except (ValueError, OverflowError, TypeError):
        parsed_iso = None
    else:
        return _normalize(parsed_iso)

    preferences: Iterable[dict[str, bool]] = _DATE_PARSE_PREFERENCES

    for options in preferences:
        try:
            parsed = date_parser.parse(normalized, **options)
        except (ValueError, OverflowError, TypeError):
            continue

        return _normalize(parsed)

    return None
