"""Adapter to make RawGeminiClient compatible with pipeline expectations.

The pipeline code expects a genai.Client with specific methods and attributes.
This adapter wraps RawGeminiClient to match that interface while using raw HTTP
calls that work properly with VCR.
"""

from __future__ import annotations

from typing import Any

from .raw_gemini_client import RawGeminiClient


class VCRCompatibleModelsAPI:
    """Models API adapter for VCR testing."""

    def __init__(self, raw_client: RawGeminiClient):
        self._raw = raw_client

    def embed_content(self, *, model: str, contents: str, config: Any = None):
        """Embed content using raw HTTP (VCR-compatible)."""
        task_type = None
        output_dim = None

        if config:
            task_type = getattr(config, "task_type", None)
            output_dim = getattr(config, "output_dimensionality", None)

        values = self._raw.embed_content(
            text=contents,
            model=model,
            task_type=task_type,
            output_dimensionality=output_dim,
        )

        # Return object that mimics genai SDK response
        return _EmbedContentResponse(values)

    def generate_content(self, *, model: str, contents: list, config: Any = None):
        """Generate content using raw HTTP (VCR-compatible)."""
        # Extract prompt from contents
        prompt = ""
        if contents and len(contents) > 0:
            content = contents[0]
            if hasattr(content, "parts"):
                for part in content.parts:
                    if hasattr(part, "text"):
                        prompt = part.text
                        break

        system_instruction = None
        if config and hasattr(config, "system_instruction"):
            sys_inst = config.system_instruction
            if sys_inst and len(sys_inst) > 0:
                part = sys_inst[0]
                if hasattr(part, "text"):
                    system_instruction = part.text

        text = self._raw.generate_content(
            prompt=prompt,
            model=model,
            system_instruction=system_instruction,
        )

        return _GenerateContentResponse(text)

    def generate_content_stream(self, *, model: str, contents: list, config: Any = None):
        """Generate content stream (not used in VCR test, just returns single chunk)."""
        response = self.generate_content(model=model, contents=contents, config=config)
        # Yield single chunk
        yield _StreamChunk(response)


class _EmbedContentResponse:
    """Mock response object that mimics genai.EmbedContentResponse."""

    def __init__(self, values: list[float]):
        self.embedding = _Embedding(values)


class _Embedding:
    """Mock embedding object."""

    def __init__(self, values: list[float]):
        self.values = values


class _GenerateContentResponse:
    """Mock response object that mimics genai.GenerateContentResponse."""

    def __init__(self, text: str):
        self.text = text
        self.candidates = [_Candidate(text)]


class _Candidate:
    """Mock candidate object."""

    def __init__(self, text: str):
        self.content = _Content(text)


class _Content:
    """Mock content object."""

    def __init__(self, text: str):
        self.parts = [_Part(text)]


class _Part:
    """Mock part object."""

    def __init__(self, text: str):
        self.text = text


class _StreamChunk:
    """Mock stream chunk."""

    def __init__(self, response: _GenerateContentResponse):
        self.text = response.text
        self.candidates = response.candidates


class VCRCompatibleClient:
    """Gemini client adapter for VCR testing.

    This wraps RawGeminiClient to match the genai.Client interface expected
    by the pipeline, while using raw HTTP calls that VCR can properly record/replay.

    Example:
        >>> import os
        >>> api_key = os.getenv("GOOGLE_API_KEY")
        >>> client = VCRCompatibleClient(api_key)
        >>>
        >>> # Use in pipeline just like genai.Client
        >>> process_whatsapp_export(..., client=client)
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._raw_client = RawGeminiClient(api_key)
        self.models = VCRCompatibleModelsAPI(self._raw_client)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._raw_client.close()

    def close(self):
        self._raw_client.close()
