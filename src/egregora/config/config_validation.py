"""Configuration validation utilities.

This module contains validation logic for config values,
extracted from CLI to maintain separation of concerns.
"""

import logging
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def parse_date_arg(date_str: str, arg_name: str = "date") -> date:
    """Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string in YYYY-MM-DD format
        arg_name: Name of the argument (for error messages)

    Returns:
        date object in UTC

    Raises:
        ValueError: If date_str is not in YYYY-MM-DD format

    Examples:
        >>> parse_date_arg("2025-01-15")
        datetime.date(2025, 1, 15)

    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC).date()
    except ValueError as e:
        msg = f"Invalid {arg_name} format: {e}. Expected format: YYYY-MM-DD"
        raise ValueError(msg) from e


def validate_retrieval_config(
    retrieval_mode: str,
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> str:
    """Validate and normalize retrieval mode configuration.

    Args:
        retrieval_mode: Retrieval strategy ('ann' or 'exact')
        retrieval_nprobe: Optional nprobe parameter for ANN
        retrieval_overfetch: Optional overfetch parameter for ANN

    Returns:
        Normalized retrieval mode string

    Raises:
        ValueError: If retrieval_mode is invalid or parameters are out of range

    """
    # Normalize retrieval mode
    normalized_mode = (retrieval_mode or "ann").lower()
    if normalized_mode not in {"ann", "exact"}:
        msg = "Invalid retrieval mode. Choose 'ann' or 'exact'."
        raise ValueError(msg)

    # Warn about incompatible options
    if normalized_mode == "exact" and retrieval_nprobe:
        logger.warning("Ignoring retrieval_nprobe: only applicable to ANN search")

    # Validate parameter ranges
    if retrieval_nprobe is not None and retrieval_nprobe <= 0:
        msg = "retrieval_nprobe must be positive when provided"
        raise ValueError(msg)

    if retrieval_overfetch is not None and retrieval_overfetch <= 0:
        msg = "retrieval_overfetch must be positive when provided"
        raise ValueError(msg)

    return normalized_mode


def validate_timezone(timezone_str: str) -> ZoneInfo:
    """Validate timezone string and return ZoneInfo object.

    Args:
        timezone_str: Timezone identifier (e.g., 'America/New_York', 'UTC')

    Returns:
        ZoneInfo object for the specified timezone

    Raises:
        ValueError: If timezone_str is not a valid timezone identifier

    Examples:
        >>> validate_timezone("UTC")
        ZoneInfo(key='UTC')
        >>> validate_timezone("America/New_York")
        ZoneInfo(key='America/New_York')

    """
    try:
        return ZoneInfo(timezone_str)
    except Exception as e:
        msg = f"Invalid timezone '{timezone_str}': {e}"
        raise ValueError(msg) from e


__all__ = [
    "parse_date_arg",
    "validate_retrieval_config",
    "validate_timezone",
]
