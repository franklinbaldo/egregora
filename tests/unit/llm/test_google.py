from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from egregora.llm.google import (
    get_google_api_key,
    get_google_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


@pytest.fixture(autouse=True)
def clear_env_vars():
    """Fixture to clear relevant environment variables before each test."""
    original_environ = os.environ.copy()
    keys_to_clear = ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMINI_API_KEYS"]
    for key in keys_to_clear:
        if key in os.environ:
            del os.environ[key]
    yield
    os.environ.clear()
    os.environ.update(original_environ)


class TestGetGoogleApiKey:
    def test_returns_google_api_key_when_set(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
        assert get_google_api_key() == "google_key"

    def test_returns_gemini_api_key_as_fallback(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
        assert get_google_api_key() == "gemini_key"

    def test_prioritizes_google_api_key_over_gemini(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
        assert get_google_api_key() == "google_key"

    def test_raises_value_error_when_no_key_is_set(self):
        with pytest.raises(ValueError, match=r"GOOGLE_API_KEY .* required"):
            get_google_api_key()


class TestGoogleApiKeyAvailable:
    def test_returns_true_if_google_api_key_is_set(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
        assert google_api_key_available() is True

    def test_returns_true_if_gemini_api_key_is_set(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
        assert google_api_key_available() is True

    def test_returns_false_if_no_key_is_set(self):
        assert google_api_key_available() is False


class TestValidateGeminiApiKey:
    @patch("google.genai.Client")
    def test_validation_successful_with_valid_key(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "valid_key")
        mock_instance = mock_client.return_value
        mock_instance.models.count_tokens.return_value = None  # Simulate successful call
        validate_gemini_api_key()
        mock_client.assert_called_once_with(api_key="valid_key")
        mock_instance.models.count_tokens.assert_called_once()

    @patch("google.genai.Client")
    def test_raises_value_error_on_invalid_key(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "invalid_key")
        mock_instance = mock_client.return_value
        mock_instance.models.count_tokens.side_effect = Exception("Invalid API key")
        with pytest.raises(ValueError, match="Invalid Gemini API key"):
            validate_gemini_api_key()

    def test_raises_import_error_if_genai_not_installed(self):
        with patch.dict("sys.modules", {"google.genai": None}):
            with pytest.raises(ImportError, match="google-genai package not installed"):
                validate_gemini_api_key()


class TestGetGoogleApiKeys:
    def test_parses_comma_separated_keys(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", "key1, key2, key3")
        assert get_google_api_keys() == ["key1", "key2", "key3"]

    def test_includes_single_gemini_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_single")
        assert get_google_api_keys() == ["gemini_single"]

    def test_includes_single_google_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google_single")
        assert get_google_api_keys() == ["google_single"]

    def test_combines_and_deduplicates_keys(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", "key1,key2")
        monkeypatch.setenv("GEMINI_API_KEY", "key2")  # Duplicate
        monkeypatch.setenv("GOOGLE_API_KEY", "key3")
        assert get_google_api_keys() == ["key1", "key2", "key3"]

    def test_returns_empty_list_when_no_keys_are_set(self):
        assert get_google_api_keys() == []

    def test_handles_whitespace_and_empty_strings(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", " key1 , , key2 , ")
        assert get_google_api_keys() == ["key1", "key2"]
