
import os
import sys
from unittest.mock import patch

import pytest

from egregora.llm.credentials import (
    get_google_api_key,
    get_google_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


@pytest.fixture
def mock_environ():
    with patch.dict(os.environ, {}, clear=True) as mock_env:
        yield mock_env


class TestGetGoogleApiKey:
    def test_get_google_api_key_from_google_api_key(self, mock_environ):
        mock_environ["GOOGLE_API_KEY"] = "google_key"
        assert get_google_api_key() == "google_key"

    def test_get_google_api_key_from_gemini_api_key(self, mock_environ):
        mock_environ["GEMINI_API_KEY"] = "gemini_key"
        assert get_google_api_key() == "gemini_key"

    def test_get_google_api_key_prefers_google_over_gemini(self, mock_environ):
        mock_environ["GOOGLE_API_KEY"] = "google_key"
        mock_environ["GEMINI_API_KEY"] = "gemini_key"
        assert get_google_api_key() == "google_key"

    def test_get_google_api_key_no_key_raises_error(self, mock_environ):
        with pytest.raises(ValueError, match="environment variable is required"):
            get_google_api_key()


class TestGoogleApiKeyAvailable:
    def test_google_api_key_available_with_google_key(self, mock_environ):
        mock_environ["GOOGLE_API_KEY"] = "google_key"
        assert google_api_key_available() is True

    def test_google_api_key_available_with_gemini_key(self, mock_environ):
        mock_environ["GEMINI_API_KEY"] = "gemini_key"
        assert google_api_key_available() is True

    def test_google_api_key_not_available(self, mock_environ):
        assert google_api_key_available() is False


class TestGetGoogleApiKeys:
    def test_get_google_api_keys_from_gemini_api_keys(self, mock_environ):
        mock_environ["GEMINI_API_KEYS"] = "key1,key2, key3"
        assert get_google_api_keys() == ["key1", "key2", "key3"]

    def test_get_google_api_keys_from_single_keys(self, mock_environ):
        mock_environ["GEMINI_API_KEY"] = "gemini_key"
        mock_environ["GOOGLE_API_KEY"] = "google_key"
        # Order is not guaranteed, so we check for presence and length
        keys = get_google_api_keys()
        assert len(keys) == 2
        assert "gemini_key" in keys
        assert "google_key" in keys

    def test_get_google_api_keys_deduplicates_keys(self, mock_environ):
        mock_environ["GEMINI_API_KEYS"] = "key1,key2"
        mock_environ["GEMINI_API_KEY"] = "key1"
        mock_environ["GOOGLE_API_KEY"] = "key3"
        keys = get_google_api_keys()
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys

    def test_get_google_api_keys_no_keys_returns_empty_list(self, mock_environ):
        assert get_google_api_keys() == []


class TestValidateGeminiApiKey:
    @patch("google.genai.Client")
    def test_validate_gemini_api_key_success(self, mock_genai_client, mock_environ):
        mock_environ["GOOGLE_API_KEY"] = "valid_key"
        validate_gemini_api_key()
        mock_genai_client.assert_called_once_with(api_key="valid_key")
        mock_genai_client.return_value.models.count_tokens.assert_called_once()

    @patch("google.genai.Client")
    def test_validate_gemini_api_key_with_explicit_key(self, mock_genai_client, mock_environ):
        validate_gemini_api_key(api_key="explicit_key")
        mock_genai_client.assert_called_once_with(api_key="explicit_key")

    @pytest.mark.parametrize(
        "error_message, expected_snippet",
        [
            ("Invalid API key", "Invalid Gemini API key"),
            ("API key not valid", "Invalid Gemini API key"),
            ("Quota exceeded", "Gemini API quota exceeded"),
            ("Permission denied", "Permission denied for Gemini API"),
            ("Forbidden: 403", "Permission denied for Gemini API"),
            ("Some other error", "Failed to validate Gemini API key"),
        ],
    )
    @patch("google.genai.Client")
    def test_validate_gemini_api_key_handles_api_errors(
        self, mock_genai_client, mock_environ, error_message, expected_snippet
    ):
        mock_environ["GOOGLE_API_KEY"] = "bad_key"
        mock_genai_client.return_value.models.count_tokens.side_effect = Exception(
            error_message
        )
        with pytest.raises(ValueError, match=expected_snippet):
            validate_gemini_api_key()

    def test_validate_gemini_api_key_import_error(self, mock_environ):
        # Simulate the 'google.genai' module not being installed
        with patch.dict(sys.modules, {"google.genai": None}):
            with pytest.raises(ImportError, match="google-genai package not installed"):
                validate_gemini_api_key()
