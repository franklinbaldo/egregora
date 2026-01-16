import os
from unittest.mock import patch

import pytest

from egregora.config.exceptions import ApiKeyNotFoundError
from egregora.config.settings import (
    _get_api_keys_from_env,
    get_google_api_key,
    get_google_api_keys,
    get_openrouter_api_key,
    get_openrouter_api_keys,
)


def test_get_google_api_key_raises_error_when_missing():
    """Test that get_google_api_key raises ApiKeyNotFoundError when env vars are not set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ApiKeyNotFoundError, match="GEMINI_API_KEY or GOOGLE_API_KEY"):
            get_google_api_key()


def test_get_google_api_key_returns_gemini_key():
    """Test that get_google_api_key returns the GEMINI_API_KEY when set."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key"}, clear=True):
        assert get_google_api_key() == "gemini_key"


def test_get_google_api_key_returns_google_key():
    """Test that get_google_api_key returns the GOOGLE_API_KEY when set."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "google_key"}, clear=True):
        assert get_google_api_key() == "google_key"


def test_get_google_api_key_prefers_gemini_key():
    """Test that GEMINI_API_KEY is preferred when both are set."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key", "GOOGLE_API_KEY": "google_key"}, clear=True):
        assert get_google_api_key() == "gemini_key"


def test_get_openrouter_api_key_raises_error_when_missing():
    """Test get_openrouter_api_key raises ApiKeyNotFoundError when the env var is not set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ApiKeyNotFoundError, match="OPENROUTER_API_KEY"):
            get_openrouter_api_key()


def test_get_openrouter_api_key_returns_key():
    """Test that get_openrouter_api_key returns the key when the env var is set."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "openrouter_key"}, clear=True):
        assert get_openrouter_api_key() == "openrouter_key"


def test_get_openrouter_api_key_strips_value():
    """Test that get_openrouter_api_key strips whitespace and equals signs."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": " = openrouter_key "}, clear=True):
        assert get_openrouter_api_key() == "openrouter_key"


def test_get_api_keys_from_env():
    """Test the helper function for parsing API keys from environment variables."""
    # Test case 1: Single key
    with patch.dict(os.environ, {"MY_KEYS": "key1"}, clear=True):
        assert _get_api_keys_from_env("MY_KEYS") == ["key1"]

    # Test case 2: Comma-separated keys with whitespace
    with patch.dict(os.environ, {"MY_KEYS": "key1, key2,key3 "}, clear=True):
        assert _get_api_keys_from_env("MY_KEYS") == ["key1", "key2", "key3"]

    # Test case 3: Empty and whitespace-only entries
    with patch.dict(os.environ, {"MY_KEYS": "key1,, key2, ,key3"}, clear=True):
        assert _get_api_keys_from_env("MY_KEYS") == ["key1", "key2", "key3"]

    # Test case 4: Duplicates
    with patch.dict(os.environ, {"MY_KEYS": "key1,key2,key1"}, clear=True):
        assert _get_api_keys_from_env("MY_KEYS") == ["key1", "key2"]

    # Test case 5: Variable not set
    with patch.dict(os.environ, {}, clear=True):
        assert _get_api_keys_from_env("MY_KEYS") == []


def test_get_google_api_keys_combines_and_deduplicates():
    """Test that get_google_api_keys combines all sources and removes duplicates."""
    env_vars = {
        "GEMINI_API_KEYS": "key1, key2",
        "GEMINI_API_KEY": "key1",
        "GOOGLE_API_KEY": "key3,key2",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        assert get_google_api_keys() == ["key1", "key2", "key3"]


def test_get_google_api_keys_empty_when_no_vars():
    """Test get_google_api_keys returns an empty list when no env vars are set."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_google_api_keys() == []


def test_get_openrouter_api_keys_combines_and_deduplicates():
    """Test that get_openrouter_api_keys combines all sources and removes duplicates."""
    env_vars = {
        "OPENROUTER_API_KEYS": "keyA, keyB",
        "OPENROUTER_API_KEY": "keyA",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        assert get_openrouter_api_keys() == ["keyA", "keyB"]


def test_get_openrouter_api_keys_empty_when_no_vars():
    """Test get_openrouter_api_keys returns an empty list when no env vars are set."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_openrouter_api_keys() == []
