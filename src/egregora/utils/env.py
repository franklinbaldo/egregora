"""Environment variable utilities for Egregora.

This module provides utilities for accessing environment variables,
particularly for API keys and credentials.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


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


def validate_gemini_api_key(api_key: str | None = None) -> None:
    """Validate Google Gemini API key with a lightweight API call.

    Uses the count_tokens endpoint which is fast and doesn't consume quota.
    This allows fail-fast validation before expensive operations.

    Args:
        api_key: API key to validate. If None, reads from environment.

    Raises:
        ValueError: If API key is invalid or API call fails

    """
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        msg = "google-genai package not installed. Install with: pip install google-genai"
        raise ImportError(msg) from e

    effective_key = api_key or get_google_api_key()

    try:
        # Use a lightweight count_tokens call to validate the key
        # This is fast and doesn't consume generation quota
        client = genai.Client(api_key=effective_key)
        client.models.count_tokens(
            model="gemini-2.0-flash-exp",
            contents=types.Content(parts=[types.Part(text="test")]),
        )
        logger.debug("Gemini API key validation successful")
    except Exception as e:
        error_msg = str(e)
        # Provide clear error message based on error type
        if "invalid" in error_msg.lower() or "api key" in error_msg.lower():
            msg = f"Invalid Gemini API key. Please check your GOOGLE_API_KEY environment variable.\nError: {error_msg}"
        elif "quota" in error_msg.lower():
            msg = f"Gemini API quota exceeded. Please check your API quota.\nError: {error_msg}"
        elif "permission" in error_msg.lower() or "403" in error_msg:
            msg = f"Permission denied for Gemini API. Please check your API key permissions.\nError: {error_msg}"
        else:
            msg = f"Failed to validate Gemini API key. Please check your network connection and API key.\nError: {error_msg}"
        raise ValueError(msg) from e


def dedupe_api_keys() -> None:
    """Remove duplicate API key environment variables to prevent SDK warnings.

    If both GOOGLE_API_KEY and GEMINI_API_KEY are set, unsets GEMINI_API_KEY
    to prevent the google-genai SDK from emitting the "Both GOOGLE_API_KEY
    and GEMINI_API_KEY are set" warning on every Client instantiation.

    Call this once at the start of the pipeline.

    """
    google_key = os.environ.get("GOOGLE_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if google_key and gemini_key:
        # If they're the same value, just unset one
        # If different, prefer GOOGLE_API_KEY (the newer/standard name)
        if google_key == gemini_key:
            logger.debug("Unsetting duplicate GEMINI_API_KEY (identical to GOOGLE_API_KEY)")
        else:
            logger.info("Both GOOGLE_API_KEY and GEMINI_API_KEY set with different values; using GOOGLE_API_KEY")
        os.environ.pop("GEMINI_API_KEY", None)


__all__ = [
    "dedupe_api_keys",
    "get_google_api_key",
    "get_google_api_keys",
    "google_api_key_available",
    "validate_gemini_api_key",
]


def get_google_api_keys() -> list[str]:
    """Get list of Google API keys from environment.

    Supports multiple keys via:
    - GEMINI_API_KEYS (comma-separated)
    - GEMINI_API_KEY (single key)
    - GOOGLE_API_KEY (single key)

    Returns:
        List of unique API keys, or empty list if none found.

    """
    keys = []

    # 1. Check GEMINI_API_KEYS (comma-separated list)
    keys_str = os.environ.get("GEMINI_API_KEYS", "")
    if keys_str:
        for k in keys_str.split(","):
            val = k.strip()
            if val and val not in keys:
                keys.append(val)

    # 2. Check individual keys
    for var in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
        val = os.environ.get(var)
        if val and val.strip() and val.strip() not in keys:
            keys.append(val.strip())

    return keys
