from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions

from src.egregora.llm.client_auth import (
    get_google_api_key,
    get_google_api_keys,
    google_api_key_available,
    validate_gemini_api_key,
)


def test_get_google_api_key_prefers_google_key():
    """Test GOOGLE_API_KEY is preferred when both are set."""
    env = {"GEMINI_API_KEY": "fallback_key", "GOOGLE_API_KEY": "preferred_key"}
    with patch.dict(os.environ, env, clear=True):
        assert get_google_api_key() == "preferred_key"


def test_get_google_api_key_falls_back_to_gemini_key():
    """Test get_google_api_key falls back to GEMINI_API_KEY."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fallback_key"}, clear=True):
        assert get_google_api_key() == "fallback_key"


def test_get_google_api_key_missing():
    """Test get_google_api_key raises ValueError when no key is set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError):
            get_google_api_key()


def test_google_api_key_available():
    """Test google_api_key_available returns True when a key is present."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}, clear=True):
        assert google_api_key_available() is True


def test_google_api_key_not_available():
    """Test google_api_key_available returns False when no key is set."""
    with patch.dict(os.environ, {}, clear=True):
        assert google_api_key_available() is False


def test_get_google_api_keys_multiple():
    """Test get_google_api_keys retrieves multiple keys correctly."""
    env_vars = {
        "GEMINI_API_KEYS": "key1,key2",
        "GEMINI_API_KEY": "key3",
        "GOOGLE_API_KEY": "key4",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        assert set(get_google_api_keys()) == {"key1", "key2", "key3", "key4"}


def test_get_google_api_keys_single():
    """Test get_google_api_keys retrieves a single key."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "single_key"}, clear=True):
        assert get_google_api_keys() == ["single_key"]


def test_get_google_api_keys_empty():
    """Test get_google_api_keys returns an empty list when no keys are set."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_google_api_keys() == []


@patch("google.genai.Client")
def test_validate_gemini_api_key_success(mock_genai_client):
    """Test validate_gemini_api_key succeeds with a valid key."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "valid_key"}, clear=True):
        validate_gemini_api_key()
    mock_client_instance.models.count_tokens.assert_called_once()


@patch("google.genai.Client")
def test_validate_gemini_api_key_invalid(mock_genai_client):
    """Test validate_gemini_api_key raises ValueError for an invalid key."""
    mock_client_instance = MagicMock()
    mock_client_instance.models.count_tokens.side_effect = exceptions.PermissionDenied("Invalid API key")
    mock_genai_client.return_value = mock_client_instance
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "invalid_key"}, clear=True):
        with pytest.raises(ValueError, match="Invalid Gemini API key"):
            validate_gemini_api_key()
