
import os
from unittest.mock import MagicMock, patch

import pytest

from egregora.llm.api_keys import (
    get_google_api_key,
    get_google_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    """Ensure a clean environment for each test."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)


class TestGetGoogleApiKey:
    def test_get_google_api_key_from_google_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
        assert get_google_api_key() == "google_key"

    def test_get_google_api_key_from_gemini_api_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
        assert get_google_api_key() == "gemini_key"

    def test_google_api_key_precedence(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
        assert get_google_api_key() == "google_key"

    def test_get_google_api_key_not_set(self):
        with pytest.raises(ValueError):
            get_google_api_key()


class TestGoogleApiKeyAvailable:
    def test_google_api_key_available_true(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        assert google_api_key_available() is True

    def test_gemini_api_key_available_true(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key")
        assert google_api_key_available() is True

    def test_api_key_available_false(self):
        assert google_api_key_available() is False


class TestGetGoogleApiKeys:
    def test_get_google_api_keys_from_gemini_api_keys(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", "key1,key2, key3")
        assert get_google_api_keys() == ["key1", "key2", "key3"]

    def test_get_google_api_keys_from_single_vars(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
        monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
        assert set(get_google_api_keys()) == {"gemini_key", "google_key"}

    def test_get_google_api_keys_mixed(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", "key1,key2")
        monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
        monkeypatch.setenv("GOOGLE_API_KEY", "google_key")
        assert set(get_google_api_keys()) == {"key1", "key2", "gemini_key", "google_key"}

    def test_get_google_api_keys_deduplication(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", "key1,key1,key2")
        monkeypatch.setenv("GEMINI_API_KEY", "key1")
        assert get_google_api_keys() == ["key1", "key2"]

    def test_get_google_api_keys_empty(self):
        assert get_google_api_keys() == []


class TestValidateGeminiApiKey:
    @patch("google.genai.Client")
    def test_validate_gemini_api_key_success(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "valid_key")
        mock_instance = mock_client.return_value
        mock_instance.models.count_tokens.return_value = None  # Simulate success
        validate_gemini_api_key()
        mock_client.assert_called_with(api_key="valid_key")
        mock_instance.models.count_tokens.assert_called_once()

    @patch("google.genai.Client")
    def test_validate_with_explicit_key(self, mock_client):
        mock_instance = mock_client.return_value
        mock_instance.models.count_tokens.return_value = None
        validate_gemini_api_key(api_key="explicit_key")
        mock_client.assert_called_with(api_key="explicit_key")

    @patch("google.genai.Client", side_effect=Exception("Invalid API key"))
    def test_validate_gemini_api_key_invalid_key(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "invalid_key")
        with pytest.raises(ValueError, match="Invalid Gemini API key"):
            validate_gemini_api_key()

    @patch("google.genai.Client", side_effect=Exception("Quota exceeded"))
    def test_validate_gemini_api_key_quota_error(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "valid_key")
        with pytest.raises(ValueError, match="Gemini API quota exceeded"):
            validate_gemini_api_key()

    @patch("google.genai.Client", side_effect=Exception("Permission denied"))
    def test_validate_gemini_api_key_permission_error(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "valid_key")
        with pytest.raises(ValueError, match="Permission denied for Gemini API"):
            validate_gemini_api_key()

    def test_validate_gemini_api_key_import_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "valid_key")
        with patch.dict('sys.modules', {'google.genai': None, 'google.genai.types': None}):
            with pytest.raises(ImportError, match="google-genai package not installed"):
                validate_gemini_api_key()
