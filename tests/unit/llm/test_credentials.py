"""Unit tests for environment variable utilities."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from egregora.llm import credentials as env


@pytest.fixture(autouse=True)
def _clear_env_vars():
    """Fixture to clear relevant environment variables before each test."""
    original_google_key = os.environ.pop("GOOGLE_API_KEY", None)
    original_gemini_key = os.environ.pop("GEMINI_API_KEY", None)
    original_gemini_keys = os.environ.pop("GEMINI_API_KEYS", None)
    yield
    if original_google_key is not None:
        os.environ["GOOGLE_API_KEY"] = original_google_key
    if original_gemini_key is not None:
        os.environ["GEMINI_API_KEY"] = original_gemini_key
    if original_gemini_keys is not None:
        os.environ["GEMINI_API_KEYS"] = original_gemini_keys


def test_get_google_api_key_from_google_api_key():
    """Test getting the API key from GOOGLE_API_KEY."""
    os.environ["GOOGLE_API_KEY"] = "google_key"
    assert env.get_google_api_key() == "google_key"


def test_get_google_api_key_from_gemini_api_key():
    """Test falling back to GEMINI_API_KEY."""
    os.environ["GEMINI_API_KEY"] = "gemini_key"
    assert env.get_google_api_key() == "gemini_key"


def test_get_google_api_key_prefers_google_over_gemini():
    """Test that GOOGLE_API_KEY is preferred over GEMINI_API_KEY."""
    os.environ["GOOGLE_API_KEY"] = "google_key"
    os.environ["GEMINI_API_KEY"] = "gemini_key"
    assert env.get_google_api_key() == "google_key"


def test_get_google_api_key_raises_error_if_not_set():
    """Test that a ValueError is raised if no key is set."""
    with pytest.raises(ValueError, match=r"GOOGLE_API_KEY.*is required"):
        env.get_google_api_key()


def test_google_api_key_available_returns_true_if_set():
    """Test that availability check returns True when a key is set."""
    os.environ["GOOGLE_API_KEY"] = "some_key"
    assert env.google_api_key_available() is True


def test_google_api_key_available_returns_false_if_not_set():
    """Test that availability check returns False when no key is set."""
    assert env.google_api_key_available() is False


def test_get_google_api_keys_from_multiple_sources():
    """Test getting keys from all supported environment variables."""
    os.environ["GEMINI_API_KEYS"] = "key1, key2,key3"
    os.environ["GEMINI_API_KEY"] = "key4"
    os.environ["GOOGLE_API_KEY"] = "key5"
    keys = env.get_google_api_keys()
    assert keys == ["key1", "key2", "key3", "key4", "key5"]


def test_get_google_api_keys_handles_duplicates():
    """Test that duplicate keys are handled correctly."""
    os.environ["GEMINI_API_KEYS"] = "key1, key2, key1"
    os.environ["GEMINI_API_KEY"] = "key2"
    os.environ["GOOGLE_API_KEY"] = "key3"
    keys = env.get_google_api_keys()
    assert keys == ["key1", "key2", "key3"]


def test_get_google_api_keys_returns_empty_list_if_none_set():
    """Test that an empty list is returned when no keys are set."""
    assert env.get_google_api_keys() == []


@patch("google.genai.Client")
def test_validate_gemini_api_key_success(mock_genai_client):
    """Test successful API key validation."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    os.environ["GOOGLE_API_KEY"] = "valid_key"
    env.validate_gemini_api_key()
    mock_genai_client.assert_called_once_with(api_key="valid_key")
    mock_client_instance.models.count_tokens.assert_called_once()


@patch("google.genai.Client")
def test_validate_gemini_api_key_with_provided_key(mock_genai_client):
    """Test validation with an explicitly provided API key."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    env.validate_gemini_api_key(api_key="provided_key")
    mock_genai_client.assert_called_once_with(api_key="provided_key")
    mock_client_instance.models.count_tokens.assert_called_once()


@patch("google.genai.Client", side_effect=Exception("Invalid API Key"))
def test_validate_gemini_api_key_raises_error_on_failure(mock_genai_client):
    """Test that a ValueError is raised on API call failure."""
    os.environ["GOOGLE_API_KEY"] = "invalid_key"
    with pytest.raises(ValueError, match="Invalid Gemini API key"):
        env.validate_gemini_api_key()
