"""Fast mock for GeminiBatchClient and genai.Client to speed up tests.

This is a temporary solution until the full golden fixtures system is implemented.
It returns fake embeddings and responses instantly without API calls.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from typing import Any
from unittest.mock import MagicMock

from google import genai
from google.genai import types as genai_types

from egregora.utils.batch import (
    BatchPromptRequest,
    BatchPromptResult,
    EmbeddingBatchRequest,
    EmbeddingBatchResult,
)


class MockGeminiBatchClient:
    """Mock batch client that returns instant fake responses."""

    def __init__(
        self,
        client: genai.Client | None = None,
        default_model: str = "models/gemini-flash-latest",
        poll_interval: float = 5.0,
        timeout: float | None = 900.0,
    ) -> None:
        """Initialize mock client (parameters match real client for compatibility)."""
        self._default_model = default_model
        # Seed random with a fixed value for deterministic tests
        self._rng = random.Random(42)

    @property
    def default_model(self) -> str:
        """Return the default model."""
        return self._default_model

    def upload_file(self, *, path: str, display_name: str | None = None) -> genai_types.File:
        """Mock file upload - returns a fake File object."""
        # Create a minimal fake File object
        return genai_types.File(
            name=f"files/{hashlib.md5(path.encode()).hexdigest()}",
            display_name=display_name or path,
            uri=f"https://mock-uri/{path}",
        )

    def generate_content(
        self,
        requests: Sequence[BatchPromptRequest],
        *,
        display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[BatchPromptResult]:
        """Mock batch generation - returns fake text responses."""
        if not requests:
            return []

        results: list[BatchPromptResult] = []
        for req in requests:
            # Create a fake response with mock text
            mock_text = f"Mock response for tag: {req.tag}"

            # Create a minimal response structure
            response = genai_types.GenerateContentResponse(
                text=mock_text,
                candidates=[
                    genai_types.Candidate(
                        content=genai_types.Content(parts=[genai_types.Part(text=mock_text)]),
                        finish_reason=genai_types.FinishReason.STOP,
                    )
                ],
            )

            results.append(
                BatchPromptResult(
                    tag=req.tag,
                    response=response,
                    error=None,
                )
            )

        return results

    def embed_content(
        self,
        requests: Sequence[EmbeddingBatchRequest],
        *,
        display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[EmbeddingBatchResult]:
        """Mock batch embedding - returns deterministic fake embeddings.

        Uses content hash to generate deterministic embeddings so same text
        always produces same embedding vector.
        """
        if not requests:
            return []

        results: list[EmbeddingBatchResult] = []

        for req in requests:
            # Generate deterministic embedding based on text content
            embedding = self._generate_fake_embedding(
                req.text,
                dimensionality=req.output_dimensionality or 3072,
            )

            results.append(
                EmbeddingBatchResult(
                    tag=req.tag,
                    embedding=embedding,
                    error=None,
                )
            )

        return results

    def _generate_fake_embedding(self, text: str, dimensionality: int = 3072) -> list[float]:
        """Generate a deterministic fake embedding vector.

        Uses MD5 hash of text as seed for reproducibility.
        Normalizes vector to unit length like real embeddings.
        """
        # Use text hash as seed for deterministic randomness
        text_hash = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = random.Random(text_hash)

        # Generate random vector
        vector = [rng.gauss(0, 1) for _ in range(dimensionality)]

        # Normalize to unit length (cosine similarity friendly)
        magnitude = sum(x * x for x in vector) ** 0.5
        normalized = [x / magnitude for x in vector]

        return normalized


class MockGeminiClient:
    """Mock genai.Client that returns fake responses instantly."""

    def __init__(self, api_key: str | None = None):
        """Initialize mock client."""
        self._api_key = api_key or "mock-key"
        self._rng = random.Random(42)

        # Create mock models interface
        self.models = MagicMock()
        self.models.generate_content = self._generate_content_sync

        # Create mock batches interface
        self.batches = MagicMock()

        # Create mock files interface
        self.files = MagicMock()
        self.files.upload = self._upload_file

    def close(self):
        """Mock close method - does nothing."""
        pass

    def _upload_file(self, file: str, **kwargs) -> genai_types.File:
        """Mock file upload."""
        return genai_types.File(
            name=f"files/{hashlib.md5(file.encode()).hexdigest()}",
            display_name=kwargs.get("display_name", file),
            uri=f"https://mock-uri/{file}",
        )

    def _generate_content_sync(
        self,
        model: str,
        contents: list[genai_types.Content] | str,
        config: Any = None,
        **kwargs,
    ) -> genai_types.GenerateContentResponse:
        """Mock synchronous generate_content."""
        # Extract text from contents
        if isinstance(contents, str):
            text = contents
        elif isinstance(contents, list):
            parts = []
            for content in contents:
                if hasattr(content, "parts"):
                    parts.extend(part.text for part in content.parts if hasattr(part, "text") and part.text)
            text = "\n".join(parts)
        else:
            text = str(contents)

        # Generate deterministic fake response based on input
        text_hash = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        _rng = random.Random(text_hash)

        # Generate mock response text
        mock_response_text = f"""---
title: Mock Generated Post
date: '2025-10-28'
tags:
- mock
- test
---

This is a mock generated post. Original content length: {len(text)} chars.
"""

        # Create response with only allowed fields
        return genai_types.GenerateContentResponse(
            candidates=[
                genai_types.Candidate(
                    content=genai_types.Content(parts=[genai_types.Part(text=mock_response_text)]),
                    finish_reason=genai_types.FinishReason.STOP,
                )
            ],
        )


def create_mock_batch_client(
    default_model: str = "models/gemini-flash-latest",
) -> MockGeminiBatchClient:
    """Factory function to create a mock batch client.

    Usage in tests:
        from tests.utils.mock_batch_client import create_mock_batch_client

        batch_client = create_mock_batch_client()
        # Use instead of real GeminiBatchClient
    """
    return MockGeminiBatchClient(default_model=default_model)


def create_mock_genai_client(api_key: str | None = None) -> MockGeminiClient:
    """Factory function to create a mock genai.Client.

    Usage in tests:
        from tests.utils.mock_batch_client import create_mock_genai_client

        client = create_mock_genai_client()
        # Use instead of real genai.Client
    """
    return MockGeminiClient(api_key=api_key)
