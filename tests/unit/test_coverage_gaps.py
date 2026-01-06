"""Tests for coverage gaps in writer and factory."""
from unittest.mock import MagicMock, patch
import pytest
from google import genai
from egregora.orchestration.factory import PipelineFactory
from egregora.agents.writer import _execute_economic_writer
from egregora.agents.types import WriterDeps, WriterResources

def test_create_gemini_client():
    """Test that create_gemini_client returns a correctly configured genai.Client."""
    with patch("google.genai.Client") as mock_client_cls:
        client = PipelineFactory.create_gemini_client()

        mock_client_cls.assert_called_once()
        call_args = mock_client_cls.call_args
        assert "http_options" in call_args[1]
        options = call_args[1]["http_options"]
        assert "retry_options" in options
        assert options["retry_options"]["attempts"] == 5

def test_execute_economic_writer():
    """Test _execute_economic_writer basic execution flow."""
    mock_config = MagicMock()
    mock_config.models.writer = "gemini-flash"
    mock_config.writer.economic_system_instruction = "test instruction"
    mock_config.writer.custom_instructions = None
    mock_config.writer.economic_temperature = 0.5

    mock_deps = MagicMock()
    mock_deps.resources.client = None
    mock_deps.window_start.strftime.return_value = "2025-01-01"
    mock_deps.window_label = "Test Window"

    # Mock the client created inside the function
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "# Summary: Title\nContent"
    mock_genai_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_genai_client):
        # We also need to patch Document creation or output.persist,
        # but output is a mock so persist is fine.
        mock_deps.resources.output.persist = MagicMock()

        saved_posts, saved_profiles = _execute_economic_writer(
            prompt="test prompt",
            config=mock_config,
            deps=mock_deps
        )

        assert len(saved_posts) == 1
        assert len(saved_profiles) == 0
        mock_genai_client.models.generate_content.assert_called_once()
