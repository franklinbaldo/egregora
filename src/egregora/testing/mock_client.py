"""Mock Gemini client for testing and demo purposes."""

from __future__ import annotations

from typing import Any


class MockGenerativeModel:
    """Mock for genai.GenerativeModel."""

    def generate_content(self, *args: Any, **kwargs: Any) -> MockGenerationResponse:
        """Mocks the generate_content method."""
        return MockGenerationResponse()


class MockGenerationResponse:
    """Mock for genai.GenerationResponse."""

    def __init__(self, text: str = "This is a mock response.") -> None:
        self._text = text
        self.parts: list[Any] = []

    @property
    def text(self) -> str:
        """Returns the mock response text."""
        return self._text


class MockModelService:
    """Mock for genai.Model."""

    def get_generative_model(self, model_name: str) -> MockGenerativeModel:
        """Mocks the get_generative_model method."""
        return MockGenerativeModel()


class MockGeminiClient:
    """A type-safe mock of the google.generativeai.Client."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the mock client."""
        self.models = MockModelService()

    def get_generative_model(self, model_name: str) -> MockGenerativeModel:
        """Mocks the get_generative_model method."""
        return self.models.get_generative_model(model_name)
