"""OpenRouter client wrapper providing Gemini-compatible interface.

This module provides a wrapper around the OpenAI SDK configured for OpenRouter,
allowing seamless integration with the existing Egregora codebase that expects
Google's genai.Client interface.
"""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI


def is_openrouter_model(model: str) -> bool:
    """Detect if a model uses OpenRouter format.

    OpenRouter models use the format: provider/model-name
    Examples: anthropic/claude-3-5-haiku:beta, google/gemini-2.0-flash-exp:free

    Args:
        model: Model identifier string

    Returns:
        True if model follows OpenRouter format (contains /)

    """
    return "/" in model


class OpenRouterClient:
    """OpenRouter client that wraps OpenAI SDK to provide Gemini-like interface.

    This class implements a subset of genai.Client methods needed by Egregora,
    routing calls to OpenRouter's OpenAI-compatible API.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)

        """
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            msg = "OPENROUTER_API_KEY environment variable or api_key parameter required"
            raise ValueError(msg)

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

    class ModelsNamespace:
        """Namespace for model operations (Gemini-compatible)."""

        def __init__(self, client: OpenAI) -> None:
            self._client = client

        def generate_content(
            self,
            model: str,
            contents: list[dict[str, Any]],
            config: Any | None = None,
        ) -> Any:
            """Generate content using OpenRouter.

            Args:
                model: Model identifier (e.g., "anthropic/claude-3-5-haiku:beta")
                contents: List of message contents in Gemini format
                config: Optional generation config

            Returns:
                Response object with .text attribute

            """
            # Convert Gemini format to OpenAI format
            messages = []
            for content in contents:
                parts = content.get("parts", [])
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                combined_text = "\n".join(text_parts)
                if combined_text:
                    messages.append({"role": "user", "content": combined_text})

            # Extract config parameters
            response_format = None
            if config and hasattr(config, "response_mime_type"):
                if config.response_mime_type == "application/json":
                    response_format = {"type": "json_object"}

            # Call OpenRouter via OpenAI SDK
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                response_format=response_format,
            )

            # Wrap in Gemini-like response object
            class Response:
                def __init__(self, openai_response: Any) -> None:
                    self.text = openai_response.choices[0].message.content
                    self._response = openai_response

            return Response(response)

    @property
    def models(self) -> ModelsNamespace:
        """Access models namespace."""
        return self.ModelsNamespace(self.client)


def create_llm_client(model: str | None = None, api_key: str | None = None) -> Any:
    """Create appropriate LLM client based on model format.

    This factory function detects whether to use OpenRouter or Gemini based on
    the model name format.

    Args:
        model: Model identifier (e.g., "gemini-1.5-flash" or "anthropic/claude-3-5-haiku")
        api_key: API key for the selected provider

    Returns:
        Either OpenRouterClient or genai.Client

    Examples:
        >>> # OpenRouter models (contain /)
        >>> client = create_llm_client("anthropic/claude-3-5-haiku:beta")
        >>> client = create_llm_client("google/gemini-2.0-flash-exp:free")

        >>> # Gemini models (no /)
        >>> client = create_llm_client("gemini-1.5-flash")
        >>> client = create_llm_client("gemini-2.0-flash-exp")

    """
    # Detect provider from model format
    if model and is_openrouter_model(model):
        # OpenRouter model
        return OpenRouterClient(api_key=api_key)

    # Default to Gemini
    from google import genai

    return genai.Client(api_key=api_key) if api_key else genai.Client()
