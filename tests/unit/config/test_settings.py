import os
from unittest.mock import patch

import pytest

from egregora.config.exceptions import ApiKeyNotFoundError
from egregora.config.settings import get_google_api_key, get_openrouter_api_key


def test_get_google_api_key_raises_error_when_missing():
    """Test that get_google_api_key raises ApiKeyNotFoundError when env vars are not set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ApiKeyNotFoundError, match="GEMINI_API_KEY or GOOGLE_API_KEY"):
            get_google_api_key()


def test_get_google_api_key_returns_gemini_key():
    """Test that get_google_api_key returns the GEMINI_API_KEY when set."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key"}, clear=True):
        assert get_google_api_key() == "gemini_key"


def test_get_google_api_key_returns_google_key():
    """Test that get_google_api_key returns the GOOGLE_API_KEY when set."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "google_key"}, clear=True):
        assert get_google_api_key() == "google_key"


def test_get_google_api_key_prefers_gemini_key():
    """Test that GEMINI_API_KEY is preferred when both are set."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_key", "GOOGLE_API_KEY": "google_key"}, clear=True):
        assert get_google_api_key() == "gemini_key"


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
