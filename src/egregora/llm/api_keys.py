"""Environment variable utilities for Egregora.

This module provides utilities for accessing environment variables,
particularly for API keys and credentials.
"""

from __future__ import annotations

import logging
import os

from egregora.config.exceptions import ApiKeyNotFoundError

logger = logging.getLogger(__name__)


def get_google_api_key() -> str:
    """Get Google API key from environment.

    Checks GOOGLE_API_KEY.

    Returns:
        The API key string

    Raises:
        ApiKeyNotFoundError: If environment variable is not set

    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY"
        raise ApiKeyNotFoundError(msg)
    return api_key


def google_api_key_available() -> bool:
    """Check if Google API key is available in environment.

    Returns:
        True if GOOGLE_API_KEY is set, False otherwise

    """
    return bool(os.environ.get("GOOGLE_API_KEY"))


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


def _get_api_keys_from_env(*env_vars: str) -> list[str]:
    """Get a de-duplicated list of API keys from multiple environment variables."""
    keys: list[str] = []
    for var in env_vars:
        keys_str = os.environ.get(var, "")
        if not keys_str:
            continue
        for k in keys_str.split(","):
            val = k.strip().lstrip("=").strip()
            if val and val not in keys:
                keys.append(val)
    return keys


def get_google_api_keys() -> list[str]:
    """Get list of Google API keys from environment.

    Supports multiple keys via:
    - GOOGLE_API_KEYS (comma-separated)
    - GOOGLE_API_KEY (single key)

    Returns:
        List of unique API keys, or empty list if none found.

    """
    return _get_api_keys_from_env("GOOGLE_API_KEYS", "GOOGLE_API_KEY")


def get_openrouter_api_key() -> str:
    """Get OpenRouter API key from environment.

    Returns:
        The API key string

    Raises:
        ApiKeyNotFoundError: If environment variable is not set

    """
    keys = get_openrouter_api_keys()
    if not keys:
        msg = "OPENROUTER_API_KEY or OPENROUTER_API_KEYS"
        raise ApiKeyNotFoundError(msg)
    return keys[0]


def get_openrouter_api_keys() -> list[str]:
    """Get list of OpenRouter API keys from environment.

    Returns:
        List of unique API keys.

    """
    return _get_api_keys_from_env("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")


__all__ = [
    "get_google_api_key",
    "get_google_api_keys",
    "get_openrouter_api_key",
    "get_openrouter_api_keys",
    "find_valid_google_api_key",
    "google_api_key_available",
    "validate_gemini_api_key",
]


def find_valid_google_api_key(api_keys: list[str]) -> tuple[str | None, list[str]]:
    """Find the first valid Google API key from a list.

    Args:
        api_keys: List of API keys to validate.

    Returns:
        Tuple containing:
        - The valid key (or None if none found)
        - List of validation error messages for invalid keys

    """
    errors: list[str] = []
    for key in api_keys:
        try:
            validate_gemini_api_key(key)
            return key, []
        except ValueError as e:
            errors.append(str(e))
    return None, errors
