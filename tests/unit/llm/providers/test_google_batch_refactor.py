"""Unit tests for the GoogleBatchModel LLM provider."""
from unittest.mock import MagicMock
import pytest
from egregora.llm.providers.google_batch import GoogleBatchModel

class TestGoogleBatchModelRefactor:
    """Tests for the GoogleBatchModel."""

    @pytest.fixture
    def model(self) -> GoogleBatchModel:
        """Fixture for GoogleBatchModel."""
        return GoogleBatchModel(api_key="test-key", model_name="gemini-1.5-flash")

    def test_response_to_dict_conversion(self, model: GoogleBatchModel):
        """
        GIVEN a mock SDK response object
        WHEN _response_to_dict is called
        THEN it should correctly convert the object to a dictionary
        """
        # Arrange: Create a mock response object with nested MagicMocks
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()

        mock_part.text = "This is a test."
        mock_content.parts = [mock_part]
        mock_content.role = "model"
        mock_candidate.content = mock_content
        mock_response.candidates = [mock_candidate]

        expected_dict = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "This is a test."}],
                        "role": "model",
                    }
                }
            ]
        }

        # Act
        result_dict = model._response_to_dict(mock_response)

        # Assert
        assert result_dict == expected_dict
