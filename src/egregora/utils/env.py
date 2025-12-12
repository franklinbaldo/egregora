"""Environment variable utilities for Egregora.

This module provides utilities for accessing environment variables,
particularly for API keys and credentials.
"""

from __future__ import annotations

import os


def get_google_api_key() -> str:
    """Get Google API key from environment.

    Checks GOOGLE_API_KEY first, then falls back to GEMINI_API_KEY
    for backward compatibility.

    Returns:
        The API key string

    Raises:
        ValueError: If neither environment variable is set

    """
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY (or GEMINI_API_KEY) environment variable is required"
        raise ValueError(msg)
    return api_key


def google_api_key_available() -> bool:
    """Check if Google API key is available in environment.

    Returns:
        True if GOOGLE_API_KEY or GEMINI_API_KEY is set, False otherwise

    """
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


__all__ = [
    "get_google_api_key",
    "google_api_key_available",
]
