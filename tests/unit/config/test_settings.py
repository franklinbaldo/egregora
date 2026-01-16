import os
from unittest.mock import patch

import pytest

from egregora.config.settings import get_google_api_keys, get_openrouter_api_keys


def test_get_google_api_keys_returns_empty_list_when_missing():
    """Test that get_google_api_keys returns an empty list when the env var is not set."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_google_api_keys() == []


def test_get_google_api_keys_returns_single_key():
    """Test that get_google_api_keys returns a single key from the new env var."""
    with patch.dict(os.environ, {"EGREGORA_GOOGLE_API_KEYS": "key1"}, clear=True):
        assert get_google_api_keys() == ["key1"]


def test_get_google_api_keys_returns_multiple_keys():
    """Test that get_google_api_keys returns multiple keys from the new env var."""
    with patch.dict(os.environ, {"EGREGORA_GOOGLE_API_KEYS": "key1,key2"}, clear=True):
        assert get_google_api_keys() == ["key1", "key2"]


def test_get_google_api_keys_ignores_old_vars():
    """Test that get_google_api_keys ignores old single-key environment variables."""
    with patch.dict(
        os.environ,
        {"GEMINI_API_KEY": "gemini_key", "GOOGLE_API_KEY": "google_key"},
        clear=True,
    ):
        assert get_google_api_keys() == []


def test_get_openrouter_api_keys_returns_empty_list_when_missing():
    """Test get_openrouter_api_keys returns an empty list when the env var is not set."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_openrouter_api_keys() == []


def test_get_openrouter_api_keys_returns_single_key():
    """Test that get_openrouter_api_keys returns a single key from the new env var."""
    with patch.dict(os.environ, {"EGREGORA_OPENROUTER_API_KEYS": "key1"}, clear=True):
        assert get_openrouter_api_keys() == ["key1"]


def test_get_openrouter_api_keys_returns_multiple_keys():
    """Test that get_openrouter_api_keys returns multiple keys from the new env var."""
    with patch.dict(os.environ, {"EGREGORA_OPENROUTER_API_KEYS": "key1, key2, =key3 "}, clear=True):
        assert get_openrouter_api_keys() == ["key1", "key2", "key3"]


def test_get_openrouter_api_keys_ignores_old_var():
    """Test that get_openrouter_api_keys ignores the old single-key environment variable."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "openrouter_key"}, clear=True):
        assert get_openrouter_api_keys() == []


def test_single_key_getters_are_removed():
    """Test that the old single-key getter functions have been removed."""
    with pytest.raises(ImportError):
        from egregora.config.settings import get_google_api_key  # noqa: F401

    with pytest.raises(ImportError):
        from egregora.config.settings import get_openrouter_api_key  # noqa: F401
