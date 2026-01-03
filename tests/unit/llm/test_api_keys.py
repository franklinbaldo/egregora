from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from egregora.llm.api_keys import (
    get_google_api_key,
    get_google_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


@patch.dict(os.environ, {}, clear=True)
def test_get_google_api_key_missing():
    """Test that getting the API key raises an error if not set."""
    with pytest.raises(ValueError):
        get_google_api_key()


@patch.dict(os.environ, {"GOOGLE_API_KEY": "google_key"}, clear=True)
def test_get_google_api_key_from_google():
    """Test that the API key is retrieved from GOOGLE_API_KEY."""
    assert get_google_api_key() == "google_key"


@patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key"}, clear=True)
def test_get_google_api_key_from_gemini_fallback():
    """Test that the API key is retrieved from GEMINI_API_KEY as a fallback."""
    assert get_google_api_key() == "gemini_key"


@patch.dict(
    os.environ,
    {"GOOGLE_API_KEY": "google_key", "GEMINI_API_KEY": "gemini_key"},
    clear=True,
)
def test_get_google_api_key_precedence():
    """Test that GOOGLE_API_KEY takes precedence over GEMINI_API_KEY."""
    assert get_google_api_key() == "google_key"


@patch.dict(os.environ, {}, clear=True)
def test_google_api_key_not_available():
    """Test that the availability check returns False when no key is set."""
    assert not google_api_key_available()


@patch.dict(os.environ, {"GOOGLE_API_KEY": "google_key"}, clear=True)
def test_google_api_key_is_available():
    """Test that the availability check returns True when a key is set."""
    assert google_api_key_available()


@patch.dict(os.environ, {}, clear=True)
def test_get_google_api_keys_empty():
    """Test that an empty list is returned when no keys are set."""
    assert get_google_api_keys() == []


@patch.dict(os.environ, {"GOOGLE_API_KEY": "key1"}, clear=True)
def test_get_google_api_keys_single_google_key():
    """Test retrieving a single key from GOOGLE_API_KEY."""
    assert get_google_api_keys() == ["key1"]


@patch.dict(os.environ, {"GEMINI_API_KEY": "key2"}, clear=True)
def test_get_google_api_keys_single_gemini_key():
    """Test retrieving a single key from GEMINI_API_KEY."""
    assert get_google_api_keys() == ["key2"]


@patch.dict(
    os.environ, {"GEMINI_API_KEYS": "key3, key4,key5 "}, clear=True
)
def test_get_google_api_keys_comma_separated():
    """Test retrieving multiple keys from GEMINI_API_KEYS."""
    assert get_google_api_keys() == ["key3", "key4", "key5"]


@patch.dict(
    os.environ,
    {
        "GEMINI_API_KEYS": "key1, key2",
        "GEMINI_API_KEY": "key3",
        "GOOGLE_API_KEY": "key4",
    },
    clear=True,
)
def test_get_google_api_keys_all_sources():
    """Test retrieving keys from all available environment variables."""
    assert get_google_api_keys() == ["key1", "key2", "key3", "key4"]


@patch.dict(
    os.environ,
    {"GEMINI_API_KEYS": "key1, key1, key2"},
    clear=True,
)
def test_get_google_api_keys_uniqueness():
    """Test that the returned list of keys contains only unique values."""
    assert get_google_api_keys() == ["key1", "key2"]


@patch("google.genai.Client")
@patch.dict(os.environ, {"GOOGLE_API_KEY": "valid_key"}, clear=True)
def test_validate_gemini_api_key_success(mock_client):
    """Test that validation passes with a valid API key."""
    # The function should complete without raising an exception.
    validate_gemini_api_key()
    mock_client.assert_called_once_with(api_key="valid_key")


@patch("google.genai.Client")
def test_validate_gemini_api_key_failure_invalid_key(mock_client):
    """Test that validation fails with a simulated invalid key error."""
    mock_client.side_effect = Exception("Invalid API key")
    with pytest.raises(ValueError, match="Invalid Gemini API key"):
        validate_gemini_api_key(api_key="invalid_key")


@patch("google.genai.Client")
def test_validate_gemini_api_key_failure_quota(mock_client):
    """Test that validation fails with a simulated quota error."""
    mock_client.side_effect = Exception("Quota exceeded")
    with pytest.raises(ValueError, match="Gemini API quota exceeded"):
        validate_gemini_api_key(api_key="quota_key")


@patch("google.genai.Client")
def test_validate_gemini_api_key_failure_permission(mock_client):
    """Test that validation fails with a simulated permission error."""
    mock_client.side_effect = Exception("Permission denied")
    with pytest.raises(ValueError, match="Permission denied for Gemini API"):
        validate_gemini_api_key(api_key="permission_key")


@patch("google.genai.Client")
def test_validate_gemini_api_key_failure_generic(mock_client):
    """Test that validation fails with a generic, unexpected error."""
    mock_client.side_effect = Exception("A generic network error")
    with pytest.raises(ValueError, match="Failed to validate Gemini API key"):
        validate_gemini_api_key(api_key="generic_key")


@patch(
    "builtins.__import__",
    side_effect=ImportError("google-genai package not installed"),
)
def test_validate_gemini_api_key_import_error(mock_import):
    """Test that an ImportError is raised if google-genai is not installed."""
    with pytest.raises(
        ImportError, match="google-genai package not installed"
    ):
        validate_gemini_api_key(api_key="any_key")
