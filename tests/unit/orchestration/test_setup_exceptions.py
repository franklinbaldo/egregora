"""Tests for setup.py exception handling."""

import os
from unittest.mock import patch, MagicMock
import pytest

from egregora.orchestration.pipelines.etl.setup import validate_api_key
from egregora.orchestration.exceptions import ApiKeyMissingError, ApiKeyInvalidError

@patch("egregora.orchestration.pipelines.etl.setup.get_google_api_keys")
@patch.dict(os.environ, clear=True)
def test_validate_api_key_raises_missing_error(mock_get_keys):
    """Test that validate_api_key raises ApiKeyMissingError when no keys are found."""
    mock_get_keys.return_value = []

    with pytest.raises(ApiKeyMissingError) as excinfo:
        validate_api_key(MagicMock())

    assert "environment variable not set" in str(excinfo.value)

@patch("egregora.orchestration.pipelines.etl.setup.get_google_api_keys")
@patch("egregora.orchestration.pipelines.etl.setup.validate_gemini_api_key")
@patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=True)
def test_validate_api_key_raises_invalid_error(mock_validate, mock_get_keys):
    """Test that validate_api_key raises ApiKeyInvalidError when validation fails."""
    mock_get_keys.return_value = ["test-key"]
    mock_validate.side_effect = ValueError("Invalid key format")

    with pytest.raises(ApiKeyInvalidError) as excinfo:
        validate_api_key(MagicMock())

    assert "All provided API keys failed validation" in str(excinfo.value)
