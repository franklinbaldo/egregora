import os
from unittest.mock import patch

import pytest

from egregora.llm.auth import get_google_api_key, get_openrouter_api_key
from egregora.llm.exceptions import ApiKeyNotFoundError


def test_get_google_api_key_raises_error_when_missing():
    """Test that get_google_api_key raises ApiKeyNotFoundError when env vars are not set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ApiKeyNotFoundError, match="GOOGLE_API_KEY or GEMINI_API_KEY"):
            get_google_api_key()


def test_get_google_api_key_returns_gemini_key():
    """Test that get_google_api_key returns the GEMINI_API_KEY when set."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key"}, clear=True):
        assert get_google_api_key() == "gemini_key"


def test_get_google_api_key_returns_google_key():
    """Test that get_google_api_key returns the GOOGLE_API_KEY when set."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "google_key"}, clear=True):
        assert get_google_api_key() == "google_key"


def test_get_google_api_key_prefers_google_key_over_gemini():
    """Test that GOOGLE_API_KEY is preferred when both are set."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key", "GOOGLE_API_KEY": "google_key"}, clear=True):
        assert get_google_api_key() == "google_key"


def test_get_openrouter_api_key_raises_error_when_missing():
    """Test get_openrouter_api_key raises ApiKeyNotFoundError when the env var is not set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ApiKeyNotFoundError, match="OPENROUTER_API_KEY"):
            get_openrouter_api_key()


def test_get_openrouter_api_key_returns_key():
    """Test that get_openrouter_api_key returns the key when the env var is set."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "openrouter_key"}, clear=True):
        assert get_openrouter_api_key() == "openrouter_key"


def test_get_openrouter_api_key_strips_value():
    """Test that get_openrouter_api_key strips whitespace and equals signs."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": " = openrouter_key "}, clear=True):
        assert get_openrouter_api_key() == "openrouter_key"


# Tests for google_api_key_available
def test_google_api_key_available_returns_true_for_google_key():
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "some_key"}, clear=True):
        from egregora.llm.auth import google_api_key_available

        assert google_api_key_available() is True


def test_google_api_key_available_returns_true_for_gemini_key():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "some_key"}, clear=True):
        from egregora.llm.auth import google_api_key_available

        assert google_api_key_available() is True


def test_google_api_key_available_returns_false_when_missing():
    with patch.dict(os.environ, {}, clear=True):
        from egregora.llm.auth import google_api_key_available

        assert google_api_key_available() is False


# Tests for get_google_api_keys
def test_get_google_api_keys_from_comma_separated_list():
    with patch.dict(os.environ, {"GEMINI_API_KEYS": "key1, key2, key3"}, clear=True):
        from egregora.llm.auth import get_google_api_keys

        assert get_google_api_keys() == ["key1", "key2", "key3"]


def test_get_google_api_keys_from_single_vars():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "key1", "GOOGLE_API_KEY": "key2"}, clear=True):
        from egregora.llm.auth import get_google_api_keys

        assert get_google_api_keys() == ["key1", "key2"]


def test_get_google_api_keys_deduplicates_keys():
    with patch.dict(os.environ, {"GEMINI_API_KEYS": "key1, key2", "GEMINI_API_KEY": "key1"}, clear=True):
        from egregora.llm.auth import get_google_api_keys

        assert get_google_api_keys() == ["key1", "key2"]


def test_get_google_api_keys_returns_empty_list_when_no_keys():
    with patch.dict(os.environ, {}, clear=True):
        from egregora.llm.auth import get_google_api_keys

        assert get_google_api_keys() == []


# Tests for validate_gemini_api_key
@patch("google.genai.Client")
def test_validate_gemini_api_key_success(mock_client):
    from egregora.llm.auth import validate_gemini_api_key

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "valid_key"}, clear=True):
        validate_gemini_api_key()
        mock_client.assert_called_with(api_key="valid_key")


@patch("google.genai.Client", side_effect=Exception("Invalid API key"))
def test_validate_gemini_api_key_failure(mock_client):
    from egregora.llm.auth import validate_gemini_api_key

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "invalid_key"}, clear=True):
        with pytest.raises(ValueError, match="Invalid Gemini API key"):
            validate_gemini_api_key()
