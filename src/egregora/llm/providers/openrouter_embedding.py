"""OpenRouter embedding provider for RAG.

Provides embedding support using OpenRouter's API, allowing access to free
embedding models like qwen/qwen3-embedding-0.6b.
"""

from __future__ import annotations

import os
from typing import Literal

import httpx

# Model dimension mappings (discovered via API or documentation)
OPENROUTER_EMBEDDING_DIMS = {
    "qwen/qwen3-embedding-0.6b": 512,  # Free model
    # Add more models as needed
}

DEFAULT_OPENROUTER_EMBEDDING_DIM = 512  # Fallback dimension


def is_openrouter_embedding_model(model: str) -> bool:
    """Detect if a model uses OpenRouter format for embeddings.

    Args:
        model: Model identifier string

    Returns:
        True if model follows OpenRouter format (contains /)

    """
    return "/" in model and not model.startswith("models/")


def get_embedding_dimension(model: str) -> int:
    """Get embedding dimension for a given model.

    Args:
        model: Model identifier (e.g., "qwen/qwen3-embedding-0.6b" or "models/gemini-embedding-001")

    Returns:
        Vector dimension for the model

    """
    if is_openrouter_embedding_model(model):
        # OpenRouter model - look up dimension
        return OPENROUTER_EMBEDDING_DIMS.get(model, DEFAULT_OPENROUTER_EMBEDDING_DIM)
    # Gemini model - use standard 768
    return 768


def embed_with_openrouter(
    texts: list[str],
    model: str = "qwen/qwen3-embedding-0.6b",
    api_key: str | None = None,
    task_type: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY"] | None = None,
) -> list[list[float]]:
    """Embed texts using OpenRouter API.

    Args:
        texts: List of texts to embed
        model: OpenRouter model identifier (e.g., "qwen/qwen3-embedding-0.6b")
        api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
        task_type: Embedding task type (ignored for OpenRouter, kept for compatibility)

    Returns:
        List of embedding vectors

    Raises:
        ValueError: If API key is missing
        httpx.HTTPError: If API request fails

    """
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        msg = "OPENROUTER_API_KEY environment variable required for OpenRouter embeddings"
        raise ValueError(msg)

    # Strip quotes from API key (common shell export issue: export KEY="value")
    api_key = api_key.strip('"').strip("'")

    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": texts,
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    # Extract embeddings from response
    # OpenAI-compatible format: {"data": [{"embedding": [...]}, ...]}
    return [item["embedding"] for item in data["data"]]
