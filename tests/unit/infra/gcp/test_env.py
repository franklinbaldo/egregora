"""Unit tests for environment variable utilities."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from egregora.infra.gcp.env import (
    get_google_api_key,
    get_google_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


@pytest.fixture(autouse=True)
def clear_env_vars():
    """Fixture to clear relevant environment variables before each test."""
    env_vars = ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMINI_API_KEYS"]
    original_values = {var: os.environ.get(var) for var in env_vars}
    for var in env_vars:
        if var in os.environ:
            del os.environ[var]
    yield
    for var, value in original_values.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]


def test_get_google_api_key_from_google_api_key(monkeypatch):
    """Test that GOOGLE_API_KEY is prioritized."""
    monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
    assert get_google_api_key() == "google_key"


def test_get_google_api_key_from_gemini_api_key(monkeypatch):
    """Test fallback to GEMINI_API_KEY."""
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
    assert get_google_api_key() == "gemini_key"


def test_get_google_api_key_no_key():
    """Test that ValueError is raised when no key is set."""
    with pytest.raises(ValueError, match="GOOGLE_API_KEY .* required"):
        get_google_api_key()


def test_google_api_key_available_true(monkeypatch):
    """Test that it returns True when a key is available."""
    monkeypatch.setenv("GEMINI_API_KEY", "some_key")
    assert google_api_key_available() is True


def test_google_api_key_available_false():
    """Test that it returns False when no key is available."""
    assert google_api_key_available() is False


@patch("google.genai.Client")
def test_validate_gemini_api_key_success(mock_genai_client, monkeypatch):
    """Test successful API key validation."""
    monkeypatch.setenv("GOOGLE_API_KEY", "valid_key")
    mock_instance = mock_genai_client.return_value
    mock_instance.models.count_tokens.return_value = None  # Simulate success
    validate_gemini_api_key()  # Should not raise


@patch("google.genai.Client")
def test_validate_gemini_api_key_invalid_key(mock_genai_client, monkeypatch):
    """Test handling of an invalid API key exception."""
    monkeypatch.setenv("GOOGLE_API_KEY", "invalid_key")
    mock_instance = mock_genai_client.return_value
    mock_instance.models.count_tokens.side_effect = Exception("Invalid API key")
    with pytest.raises(ValueError, match="Invalid Gemini API key"):
        validate_gemini_api_key()


def test_get_google_api_keys_from_multiple_sources(monkeypatch):
    """Test getting keys from all supported environment variables."""
    monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
    monkeypatch.setenv("GEMINI_API_KEYS", "key1,key2, key3")
    keys = get_google_api_keys()
    assert set(keys) == {"google_key", "gemini_key", "key1", "key2", "key3"}
    # Check order: GEMINI_API_KEYS, then GEMINI_API_KEY, then GOOGLE_API_KEY
    assert keys == ["key1", "key2", "key3", "gemini_key", "google_key"]


def test_get_google_api_keys_handles_duplicates(monkeypatch):
    """Test that duplicate keys are handled correctly."""
    monkeypatch.setenv("GOOGLE_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY", "key2")
    monkeypatch.setenv("GEMINI_API_KEYS", "key1, key2, key3")
    keys = get_google_api_keys()
    assert keys == ["key1", "key2", "key3"]


def test_get_google_api_keys_no_keys():
    """Test that an empty list is returned when no keys are set."""
    assert get_google_api_keys() == []


@patch.dict("sys.modules", {"google.genai": None})
def test_validate_gemini_api_key_importerror(monkeypatch):
    """Test that an ImportError is raised if google-genai is not installed."""
    monkeypatch.setenv("GOOGLE_API_KEY", "a_key")
    # We need to unload the real module if it's already loaded
    if "google.genai" in globals():
        del globals()["google.genai"]

    with pytest.raises(ImportError, match="google-genai package not installed"):
        # This will fail because the import inside the function will fail
        validate_gemini_api_key()
