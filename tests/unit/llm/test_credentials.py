import os
from unittest.mock import MagicMock, patch

import pytest

from egregora.llm.credentials import (
    get_google_api_key,
    get_google_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


@pytest.fixture(autouse=True)
def clear_env_vars():
    """Clear relevant environment variables before and after each test."""
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


def test_get_google_api_key_from_google_api_key():
    os.environ["GOOGLE_API_KEY"] = "google_key"
    assert get_google_api_key() == "google_key"


def test_get_google_api_key_from_gemini_api_key():
    os.environ["GEMINI_API_KEY"] = "gemini_key"
    assert get_google_api_key() == "gemini_key"


def test_get_google_api_key_prefers_google_over_gemini():
    os.environ["GOOGLE_API_KEY"] = "google_key"
    os.environ["GEMINI_API_KEY"] = "gemini_key"
    assert get_google_api_key() == "google_key"


def test_get_google_api_key_raises_error_if_not_set():
    with pytest.raises(ValueError, match="is required"):
        get_google_api_key()


def test_google_api_key_available_is_true_if_google_api_key_set():
    os.environ["GOOGLE_API_KEY"] = "google_key"
    assert google_api_key_available() is True


def test_google_api_key_available_is_true_if_gemini_api_key_set():
    os.environ["GEMINI_API_KEY"] = "gemini_key"
    assert google_api_key_available() is True


def test_google_api_key_available_is_false_if_no_key_set():
    assert google_api_key_available() is False


@patch("google.genai.Client")
def test_validate_gemini_api_key_successful(mock_genai_client):
    os.environ["GOOGLE_API_KEY"] = "valid_key"
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    validate_gemini_api_key()
    mock_client_instance.models.count_tokens.assert_called_once()


@patch("google.genai.Client")
def test_validate_gemini_api_key_invalid_key(mock_genai_client):
    os.environ["GOOGLE_API_KEY"] = "invalid_key"
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    mock_client_instance.models.count_tokens.side_effect = Exception("Invalid API key")
    with pytest.raises(ValueError, match="Invalid Gemini API key"):
        validate_gemini_api_key()


def test_get_google_api_keys_from_gemini_api_keys():
    os.environ["GEMINI_API_KEYS"] = "key1,key2, key3"
    assert get_google_api_keys() == ["key1", "key2", "key3"]


def test_get_google_api_keys_from_single_keys():
    os.environ["GEMINI_API_KEY"] = "gemini_key"
    os.environ["GOOGLE_API_KEY"] = "google_key"
    assert get_google_api_keys() == ["gemini_key", "google_key"]


def test_get_google_api_keys_deduplicates_keys():
    os.environ["GEMINI_API_KEYS"] = "key1,key2,key1"
    os.environ["GEMINI_API_KEY"] = "key2"
    os.environ["GOOGLE_API_KEY"] = "key3"
    assert get_google_api_keys() == ["key1", "key2", "key3"]


def test_get_google_api_keys_empty_if_not_set():
    assert get_google_api_keys() == []
