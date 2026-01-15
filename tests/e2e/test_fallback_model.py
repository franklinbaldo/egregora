"""E2E test for the fallback model."""
from __future__ import annotations
from unittest.mock import patch
from egregora.llm.model_fallback import create_fallback_model
from egregora.testing.mock_client import MockGenerativeModel
def test_fallback_model():
    """Test the fallback model."""
    with patch("egregora.llm.providers.google_batch.genai", new=MockGenerativeModel):
        model = create_fallback_model("gemini-pro", "This is a canned response.")
        assert model is None
