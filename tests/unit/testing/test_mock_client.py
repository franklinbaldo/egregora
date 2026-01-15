"""Unit tests for the mock Gemini client."""
from __future__ import annotations

import pytest

from egregora.testing.mock_client import (
    MockGeminiClient,
    MockGenerationResponse,
    MockGenerativeModel,
)


def test_mock_generation_response():
    """Test that the mock response returns the correct text."""
    response = MockGenerationResponse(text="Custom mock response")
    assert response.text == "Custom mock response"

    # Test default text
    default_response = MockGenerationResponse()
    assert default_response.text == "This is a mock response."


def test_mock_generative_model():
    """Test that the mock model's generate_content returns a mock response."""
    model = MockGenerativeModel()
    response = model.generate_content("What is the meaning of life?")
    assert isinstance(response, MockGenerationResponse)
    assert response.text == "This is a mock response."


def test_mock_gemini_client():
    """Test that the mock client can create a generative model."""
    client = MockGeminiClient()
    model = client.get_generative_model("gemini-1.5-pro")
    assert isinstance(model, MockGenerativeModel)

    # Ensure it returns the same type of object as the model service
    model_from_service = client.models.get_generative_model("gemini-1.5-pro")
    assert isinstance(model_from_service, MockGenerativeModel)
