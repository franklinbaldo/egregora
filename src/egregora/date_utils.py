"""Utility helpers for parsing WhatsApp date strings."""

from datetime import datetime, date


def parse_flexible_date(token: str) -> date | None:
    """Parse dates in either DD/MM/YYYY or MM/DD/YYYY formats."""

    normalized = token.strip()

    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%m/%d/%y"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue

    return None
