import os
from unittest.mock import patch

import pytest
from google.api_core import exceptions

# Assuming the functions are in the new module, so I'm updating the import path
from egregora.llm.client import (
    get_google_api_key,
    get_google_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


# --- Tests for get_google_api_key ---
def test_get_google_api_key_prefers_google_key():
    """Test get_google_api_key prefers GOOGLE_API_KEY over GEMINI_API_KEY."""
    env = {"GOOGLE_API_KEY": "google_key", "GEMINI_API_KEY": "gemini_key"}
    with patch.dict(os.environ, env, clear=True):
        assert get_google_api_key() == "google_key"


def test_get_google_api_key_falls_back_to_gemini_key():
    """Test get_google_api_key falls back to GEMINI_API_KEY."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key"}, clear=True):
        assert get_google_api_key() == "gemini_key"


def test_get_google_api_key_raises_error_if_no_key():
    """Test get_google_api_key raises ValueError if no key is set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            get_google_api_key()


# --- Tests for google_api_key_available ---
def test_google_api_key_is_available():
    """Test google_api_key_available returns True if a key is set."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "some_key"}, clear=True):
        assert google_api_key_available()


def test_google_api_key_is_not_available():
    """Test google_api_key_available returns False if no key is set."""
    with patch.dict(os.environ, {}, clear=True):
        assert not google_api_key_available()


# --- Tests for get_google_api_keys ---
def test_get_google_api_keys_from_multiple_sources():
    """Test get_google_api_keys collects and deduplicates keys."""
    env = {
        "GEMINI_API_KEYS": "key1,key2",
        "GEMINI_API_KEY": "key2",
        "GOOGLE_API_KEY": "key3",
    }
    with patch.dict(os.environ, env, clear=True):
        assert sorted(get_google_api_keys()) == sorted(["key1", "key2", "key3"])


def test_get_google_api_keys_returns_empty_list_if_none():
    """Test get_google_api_keys returns an empty list if no keys are found."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_google_api_keys() == []


# --- Tests for validate_gemini_api_key ---
@patch("google.genai.Client")
def test_validate_gemini_api_key_success(mock_client):
    """Test validate_gemini_api_key passes with a valid key."""
    instance = mock_client.return_value
    instance.models.count_tokens.return_value = None  # Success
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "valid_key"}):
        validate_gemini_api_key()  # Should not raise


@patch("google.genai.Client")
def test_validate_gemini_api_key_raises_on_invalid_key(mock_client):
    """Test validate_gemini_api_key raises ValueError on API error."""
    instance = mock_client.return_value
    instance.models.count_tokens.side_effect = exceptions.PermissionDenied("Invalid API key")
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "invalid_key"}):
        with pytest.raises(ValueError, match="Invalid Gemini API key"):
            validate_gemini_api_key()
