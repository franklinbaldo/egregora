"""Tests for coverage gaps in writer and factory."""

from unittest.mock import patch

from egregora.orchestration.factory import PipelineFactory


def test_create_gemini_client():
    """Test that create_gemini_client returns a correctly configured genai.Client."""
    with patch("google.genai.Client") as mock_client_cls:
        PipelineFactory.create_gemini_client()

        mock_client_cls.assert_called_once()
        call_args = mock_client_cls.call_args
        assert "http_options" in call_args[1]
        options = call_args[1]["http_options"]
        assert "retry_options" in options
        assert options["retry_options"]["attempts"] == 5
