"""Tests for the model_fallback utility."""
from __future__ import annotations

import httpx
import pytest

from egregora.utils.exceptions import ModelConfigurationError, OpenRouterAPIError
from egregora.utils.model_fallback import (
    create_fallback_model,
    get_openrouter_free_models,
)


def test_get_openrouter_free_models_raises_on_http_error(monkeypatch):
    """Verify that get_openrouter_free_models raises OpenRouterAPIError on HTTP error."""

    def mock_get(*args, **kwargs):
        raise httpx.HTTPError("Test HTTP Error")

    monkeypatch.setattr(httpx, "get", mock_get)

    with pytest.raises(OpenRouterAPIError):
        get_openrouter_free_models()


def test_create_fallback_model_raises_on_unknown_model_type():
    """Verify that create_fallback_model raises ModelConfigurationError for unknown model types."""
    with pytest.raises(ModelConfigurationError):
        create_fallback_model(123)


def test_create_fallback_model_raises_on_missing_openrouter_key(monkeypatch):
    """Verify that create_fallback_model raises ModelConfigurationError if OPENROUTER_API_KEY is missing."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ModelConfigurationError):
        create_fallback_model("openrouter:test-model")
