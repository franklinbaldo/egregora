"""Unit tests for LLM API key utilities."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from egregora.llm import api_keys as env


@pytest.fixture(autouse=True)
def _clear_env_vars(monkeypatch: pytest.MonkeyPatch):
    """Ensure a clean environment for each test."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)


def test_get_google_api_key_from_google_api_key(monkeypatch: pytest.MonkeyPatch):
    """It should return the key from GOOGLE_API_KEY if set."""
    monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
    assert env.get_google_api_key() == "google_key"


def test_get_google_api_key_from_gemini_api_key(monkeypatch: pytest.MonkeyPatch):
    """It should fall back to GEMINI_API_KEY if GOOGLE_API_KEY is not set."""
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
    assert env.get_google_api_key() == "gemini_key"


def test_get_google_api_key_prefers_google_over_gemini(monkeypatch: pytest.MonkeyPatch):
    """It should prefer GOOGLE_API_KEY when both are set."""
    monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
    assert env.get_google_api_key() == "google_key"


def test_get_google_api_key_raises_error_if_not_set():
    """It should raise a ValueError if no key is set."""
    with pytest.raises(
        ValueError, match="GOOGLE_API_KEY .* environment variable is required"
    ):
        env.get_google_api_key()


def test_google_api_key_available_returns_true_if_set(monkeypatch: pytest.MonkeyPatch):
    """It should return True if GOOGLE_API_KEY is available."""
    monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
    assert env.google_api_key_available() is True


def test_google_api_key_available_returns_true_for_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    """It should return True if GEMINI_API_KEY is available."""
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
    assert env.google_api_key_available() is True


def test_google_api_key_available_returns_false_if_not_set():
    """It should return False if no key is set."""
    assert env.google_api_key_available() is False


@patch("google.genai.Client")
def test_validate_gemini_api_key_success(
    mock_genai_client: MagicMock, monkeypatch: pytest.MonkeyPatch
):
    """It should not raise an error for a valid key."""
    monkeypatch.setenv("GOOGLE_API_KEY", "valid_key")
    # Mock the client and its methods to simulate a successful API call
    mock_instance = mock_genai_client.return_value
    mock_instance.models.count_tokens.return_value = None  # Simulate success

    try:
        env.validate_gemini_api_key()
    except ValueError:
        pytest.fail("validate_gemini_api_key() raised ValueError unexpectedly!")


@patch("google.genai.Client")
def test_validate_gemini_api_key_failure(
    mock_genai_client: MagicMock, monkeypatch: pytest.MonkeyPatch
):
    """It should raise a ValueError for an invalid key."""
    monkeypatch.setenv("GOOGLE_API_KEY", "invalid_key")
    # Mock the client to simulate an API error
    mock_instance = mock_genai_client.return_value
    mock_instance.models.count_tokens.side_effect = Exception("Invalid API key")

    with pytest.raises(ValueError, match="Invalid Gemini API key"):
        env.validate_gemini_api_key()


def test_get_google_api_keys_from_multiple_sources(monkeypatch: pytest.MonkeyPatch):
    """It should collect unique keys from all supported environment variables."""
    monkeypatch.setenv("GEMINI_API_KEYS", "key1, key2, key3")
    monkeypatch.setenv("GEMINI_API_KEY", "key4")
    monkeypatch.setenv("GOOGLE_API_KEY", "key1")  # Duplicates should be ignored
    keys = env.get_google_api_keys()
    assert sorted(keys) == sorted(["key1", "key2", "key3", "key4"])


def test_get_google_api_keys_empty_if_none_set():
    """It should return an empty list if no keys are set."""
    assert env.get_google_api_keys() == []


def test_get_google_api_keys_handles_whitespace(monkeypatch: pytest.MonkeyPatch):
    """It should handle whitespace in comma-separated lists."""
    monkeypatch.setenv("GEMINI_API_KEYS", "  key1,  key2  ")
    assert env.get_google_api_keys() == ["key1", "key2"]
