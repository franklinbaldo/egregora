"""Logfire configuration for observability.

This module provides centralized Logfire setup for the Pydantic AI backend.
Logfire is only configured when LOGFIRE_TOKEN is set in the environment.
"""

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def configure_logfire() -> bool:
    """Configure Logfire if token is available.

    Returns:
        bool: True if Logfire was configured, False otherwise

    """
    token = os.environ.get("LOGFIRE_TOKEN")
    if not token:
        logger.info("LOGFIRE_TOKEN not set, skipping Logfire configuration")
        return False
    try:
        import logfire

        logfire.configure(token=token)
        logger.info("Logfire configured successfully")
        return True
    except ImportError:
        logger.warning("logfire package not installed, skipping configuration")
        return False


def get_logfire():
    """Get logfire module if available.

    Returns:
        logfire module or None if not available

    """
    try:
        import logfire
    except ImportError:
        return None
    else:
        return logfire


def logfire_span(name: str, **kwargs):
    """Create a Logfire span if available, otherwise no-op context manager.

    Args:
        name: Span name
        **kwargs: Additional span attributes

    Returns:
        Context manager (span or nullcontext)

    """
    logfire = get_logfire()
    if logfire and configure_logfire():
        return logfire.span(name, **kwargs)
    from contextlib import nullcontext

    return nullcontext()


def logfire_info(message: str, **kwargs) -> None:
    """Log info message to Logfire if available.

    Args:
        message: Log message
        **kwargs: Additional log attributes

    """
    logfire = get_logfire()
    if logfire and configure_logfire():
        logfire.info(message, **kwargs)
