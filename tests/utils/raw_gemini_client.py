"""Raw HTTP client for Gemini API - VCR-compatible alternative to genai SDK.

This module provides HTTP-level access to Gemini API endpoints for testing with VCR.
The official genai SDK uses complex response parsing that doesn't work with VCR replay,
so this wrapper uses direct httpx calls that VCR can properly record and replay.

This is ONLY for testing - production code should use the official genai SDK.
"""

from __future__ import annotations

from typing import Any

import httpx


class RawGeminiClient:
    """HTTP-only Gemini client for VCR testing.

    This client makes direct HTTP calls to Gemini API endpoints, bypassing the
    official SDK's response parsing. This allows VCR to properly record and replay
    API interactions for end-to-end testing.

    Example:
        >>> client = RawGeminiClient(api_key="your-key")
        >>> embedding = client.embed_content("hello world", "gemini-embedding-001")
        >>> print(len(embedding))  # 768 or 3072 depending on model

    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, timeout: float = 30.0):
        """Initialize raw HTTP client.

        Args:
            api_key: Gemini API key
            timeout: Request timeout in seconds

        """
        self.api_key = api_key
        self.timeout = timeout
        self._http_client = httpx.Client(timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._http_client.close()

    def embed_content(
        self,
        text: str,
        model: str = "gemini-embedding-001",
        task_type: str | None = None,
        output_dimensionality: int | None = None,
    ) -> list[float]:
        """Generate embedding for text using direct HTTP call.

        Args:
            text: Text to embed
            model: Embedding model name (may include "models/" prefix)
            task_type: Optional task type (e.g., "RETRIEVAL_QUERY")
            output_dimensionality: Optional output dimensionality (e.g., 768, 3072)

        Returns:
            List of embedding values

        Raises:
            httpx.HTTPError: If request fails

        """
        # Strip any leading "models/" prefix to avoid double-prefixing in the URL.
        while model.startswith("models/"):
            model = model[7:]

        url = f"{self.BASE_URL}/models/{model}:embedContent"

        payload: dict[str, Any] = {"content": {"parts": [{"text": text}]}}

        if task_type or output_dimensionality:
            config: dict[str, Any] = {}
            if task_type:
                config["taskType"] = task_type
            if output_dimensionality:
                config["outputDimensionality"] = output_dimensionality
            payload["config"] = config

        response = self._http_client.post(
            url,
            json=payload,
            params={"key": self.api_key},
        )
        response.raise_for_status()

        data = response.json()
        return data["embedding"]["values"]

    def batch_embed_content(
        self,
        texts: list[str],
        model: str = "gemini-embedding-001",
        task_type: str | None = None,
        output_dimensionality: int | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts using batch endpoint.

        Args:
            texts: List of texts to embed
            model: Embedding model name (may include "models/" prefix)
            task_type: Optional task type
            output_dimensionality: Optional output dimensionality

        Returns:
            List of embedding vectors (one per input text)

        """
        # Strip any leading "models/" prefix to avoid double-prefixing in the URL.
        while model.startswith("models/"):
            model = model[7:]

        url = f"{self.BASE_URL}/models/{model}:batchEmbedContents"

        requests_payload = []
        for text in texts:
            req: dict[str, Any] = {"content": {"parts": [{"text": text}], "role": "user"}}
            if task_type:
                req["taskType"] = task_type
            if output_dimensionality:
                req["outputDimensionality"] = output_dimensionality

            requests_payload.append(req)

        payload = {"requests": requests_payload}

        response = self._http_client.post(
            url,
            json=payload,
            params={"key": self.api_key},
        )
        response.raise_for_status()

        data = response.json()
        return [emb["values"] for emb in data["embeddings"]]

    def generate_content(
        self,
        prompt: str,
        model: str = "gemini-flash-latest",
        system_instruction: str | None = None,
    ) -> str:
        """Generate text content using direct HTTP call.

        Args:
            prompt: User prompt
            model: Generation model name (may include "models/" prefix)
            system_instruction: Optional system instruction

        Returns:
            Generated text content

        """
        # Strip any leading "models/" prefix to avoid double-prefixing in the URL.
        while model.startswith("models/"):
            model = model[7:]

        url = f"{self.BASE_URL}/models/{model}:generateContent"

        payload: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        response = self._http_client.post(
            url,
            json=payload,
            params={"key": self.api_key},
        )
        response.raise_for_status()

        data = response.json()
        # Extract text from first candidate
        if data.get("candidates"):
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                if parts and "text" in parts[0]:
                    return parts[0]["text"]

        return ""

    def close(self):
        """Close the HTTP client."""
        self._http_client.close()


def create_raw_client_from_genai(genai_client: Any) -> RawGeminiClient:
    """Create a RawGeminiClient from an existing genai.Client.

    This helper extracts the API key from the official SDK client and creates
    a raw HTTP client for VCR testing.

    Args:
        genai_client: google.genai.Client instance

    Returns:
        RawGeminiClient configured with same API key

    """
    # Extract API key from genai client
    api_key = getattr(genai_client, "api_key", None)
    if not api_key:
        # Try to get from _api_client
        api_client = getattr(genai_client, "_api_client", None)
        if api_client:
            api_key = getattr(api_client, "_api_key", None)

    if not api_key:
        raise ValueError("Could not extract API key from genai.Client")

    return RawGeminiClient(api_key=api_key)
