"""Date and time utility functions.

MODERN (Phase 3): Consolidated datetime helpers to avoid duplication.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def ensure_datetime(value: datetime | str | pd.Timestamp) -> datetime:  # type: ignore[name-defined]
    """Convert various datetime representations to Python datetime.

    Handles multiple input types:
    - datetime: returns as-is
    - str: parses as ISO 8601 timestamp
    - pandas.Timestamp: converts via to_pydatetime()

    Args:
        value: Datetime value in various formats

    Returns:
        Python datetime object

    Raises:
        ValueError: If string cannot be parsed as ISO timestamp
        TypeError: If value type is not supported

    Examples:
        >>> from datetime import datetime
        >>> ensure_datetime(datetime(2025, 1, 15))
        datetime.datetime(2025, 1, 15, 0, 0)

        >>> ensure_datetime("2025-01-15T10:00:00")
        datetime.datetime(2025, 1, 15, 10, 0)

    """
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as e:
            msg = f"Cannot parse datetime from string: {value}"
            raise ValueError(msg) from e

    # Handle pandas.Timestamp (avoid import at module level)
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()  # type: ignore[union-attr]

    msg = f"Unsupported datetime type: {type(value)}"
    raise TypeError(msg)


__all__ = ["ensure_datetime"]
