from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from egregora.config.exceptions import ApiKeyNotFoundError
from egregora.llm.api_keys import (
    _get_api_keys_from_env,
    find_valid_google_api_key,
    get_google_api_key,
    get_google_api_keys,
    get_openrouter_api_key,
    get_openrouter_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


@patch.dict(os.environ, {}, clear=True)
def test_get_google_api_key_missing():
    """Test that getting the API key raises an error if not set."""
    with pytest.raises(
        ApiKeyNotFoundError,
        match="API key environment variable not set: GOOGLE_API_KEY",
    ):
        get_google_api_key()


@patch.dict(os.environ, {"GOOGLE_API_KEY": "google_key"}, clear=True)
def test_get_google_api_key_from_google():
    """Test that the API key is retrieved from GOOGLE_API_KEY."""
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


@patch.dict(os.environ, {"GOOGLE_API_KEYS": "key1, key2"}, clear=True)
def test_get_google_api_keys_comma_separated():
    """Test retrieving multiple keys from GOOGLE_API_KEYS."""
    assert get_google_api_keys() == ["key1", "key2"]


@patch.dict(
    os.environ,
    {"GOOGLE_API_KEYS": "key1, key1, key2"},
    clear=True,
)
def test_get_google_api_keys_uniqueness():
    """Test that the returned list of keys contains only unique values."""
    assert get_google_api_keys() == ["key1", "key2"]


@patch.dict(os.environ, {}, clear=True)
def test_get_openrouter_api_key_missing():
    """Test that getting the OpenRouter key raises an error if not set."""
    with pytest.raises(
        ApiKeyNotFoundError,
        match="API key environment variable not set: OPENROUTER_API_KEY or OPENROUTER_API_KEYS",
    ):
        get_openrouter_api_key()


@patch.dict(os.environ, {"OPENROUTER_API_KEY": "or_key"}, clear=True)
def test_get_openrouter_api_key_success():
    """Test that the OpenRouter key is retrieved."""
    assert get_openrouter_api_key() == "or_key"


@patch.dict(os.environ, {"OPENROUTER_API_KEYS": "key1,key2"}, clear=True)
def test_get_openrouter_api_keys_success():
    """Test that OpenRouter keys are retrieved correctly."""
    assert get_openrouter_api_keys() == ["key1", "key2"]


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


def test_validate_gemini_api_key_import_error():
    """Test that an ImportError is raised if google-genai is not installed."""
    with patch(
        "builtins.__import__",
        side_effect=ImportError("google-genai package not installed"),
    ):
        with pytest.raises(ImportError, match="google-genai package not installed"):
            validate_gemini_api_key(api_key="any_key")


@patch("egregora.llm.api_keys.validate_gemini_api_key")
def test_find_valid_google_api_key_first_valid(mock_validate):
    """Test finding a valid key when the first one is valid."""
    keys = ["valid_key", "other_key"]
    # No exception raised means valid
    key, errors = find_valid_google_api_key(keys)
    assert key == "valid_key"
    assert errors == []
    mock_validate.assert_called_once_with("valid_key")


@patch("egregora.llm.api_keys.validate_gemini_api_key")
def test_find_valid_google_api_key_second_valid(mock_validate):
    """Test finding a valid key when the second one is valid."""
    keys = ["invalid_key", "valid_key"]

    # First call raises ValueError, second passes
    mock_validate.side_effect = [ValueError("Invalid key"), None]

    key, errors = find_valid_google_api_key(keys)
    assert key == "valid_key"
    assert errors == []  # Errors are only returned if NO valid key is found?
    # Wait, my implementation accumulates errors but returns them only if no key found?
    # Let's check implementation:
    #     errors = []
    #     for key in api_keys:
    #         try:
    #             validate_gemini_api_key(key)
    #             return key, []  <-- Returns empty list if found
    #         except ValueError as e:
    #             errors.append(str(e))
    #     return None, errors

    assert mock_validate.call_count == 2


@patch("egregora.llm.api_keys.validate_gemini_api_key")
def test_find_valid_google_api_key_all_invalid(mock_validate):
    """Test when all keys are invalid."""
    keys = ["invalid1", "invalid2"]
    mock_validate.side_effect = [ValueError("Error 1"), ValueError("Error 2")]

    key, errors = find_valid_google_api_key(keys)
    assert key is None
    assert errors == ["Error 1", "Error 2"]
    assert mock_validate.call_count == 2


def test_find_valid_google_api_key_empty():
    """Test when input list is empty."""
    key, errors = find_valid_google_api_key([])
    assert key is None
    assert errors == []
