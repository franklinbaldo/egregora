"""Configuration validation utilities.

This module contains validation logic for config values,
extracted from CLI to maintain separation of concerns.
"""

import logging
from datetime import UTC, date, datetime

from egregora.config.settings import ProcessConfig

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


def validate_retrieval_config(config: ProcessConfig) -> None:
    """Validate and normalize retrieval mode configuration.

    Modifies config in place to normalize retrieval_mode and validate parameters.

    Args:
        config: ProcessConfig to validate (modified in place)

    Raises:
        ValueError: If retrieval_mode is invalid or parameters are out of range

    """
    # Normalize retrieval mode
    retrieval_mode = (config.retrieval_mode or "ann").lower()
    if retrieval_mode not in {"ann", "exact"}:
        msg = "Invalid retrieval mode. Choose 'ann' or 'exact'."
        raise ValueError(msg)

    # Warn about incompatible options
    if retrieval_mode == "exact" and config.retrieval_nprobe:
        logger.warning("Ignoring retrieval_nprobe: only applicable to ANN search")
        config.retrieval_nprobe = None

    # Validate parameter ranges
    if config.retrieval_nprobe is not None and config.retrieval_nprobe <= 0:
        msg = "retrieval_nprobe must be positive when provided"
        raise ValueError(msg)

    if config.retrieval_overfetch is not None and config.retrieval_overfetch <= 0:
        msg = "retrieval_overfetch must be positive when provided"
        raise ValueError(msg)

    # Update config with normalized mode
    config.retrieval_mode = retrieval_mode


__all__ = [
    "parse_date_arg",
    "validate_retrieval_config",
]
