"""Jina AI Embedding Provider.

Jina AI provides high-quality multilingual embedding models via API.

Supported Models:
- jina-embeddings-v3: 1024 dimensions (truncatable to 32)
- jina-embeddings-v4: 2048 dimensions (truncatable to 128)

API Documentation: https://jina.ai/embeddings/
"""

from __future__ import annotations

import os
from typing import Literal

import httpx

# Model dimension mapping
JINA_EMBEDDING_DIMS = {
    "jina-embeddings-v3": 1024,
    "jina-ai/jina-embeddings-v3": 1024,
    "jinaai/jina-embeddings-v3": 1024,
    "jina-embeddings-v4": 2048,
    "jina-ai/jina-embeddings-v4": 2048,
    "jinaai/jina-embeddings-v4": 2048,
}

# Default model
DEFAULT_JINA_MODEL = "jina-embeddings-v3"


def is_jina_embedding_model(model: str) -> bool:
    """Check if a model string is a Jina embedding model.

    Jina models are identified by:
    - Starting with "jina-embeddings-" or
    - Containing "jina-ai/" or "jinaai/" prefix

    Args:
        model: Model identifier string

    Returns:
        True if this is a Jina model format

    """
    model_lower = model.lower()
    return model_lower.startswith("jina-embeddings-") or "jina-ai/" in model_lower or "jinaai/" in model_lower


def get_embedding_dimension(model: str) -> int:
    """Get the embedding dimension for a Jina model.

    Args:
        model: Model identifier

    Returns:
        Embedding dimension (1024 for v3, 2048 for v4, 1024 default)

    """
    if is_jina_embedding_model(model):
        return JINA_EMBEDDING_DIMS.get(model, 1024)
    # For non-Jina models, delegate to other providers
    return 768  # Fallback (will be handled by other providers)


def embed_with_jina(
    texts: list[str],
    model: str = DEFAULT_JINA_MODEL,
    api_key: str | None = None,
    task: Literal[
        "retrieval.query",
        "retrieval.passage",
        "text-matching",
        "classification",
        "separation",
    ]
    | None = None,
    *,
    normalized: bool = True,
) -> list[list[float]]:
    """Embed texts using Jina AI API.

    Args:
        texts: List of texts to embed
        model: Jina model identifier (default: jina-embeddings-v3)
        api_key: Jina API key (defaults to JINA_API_KEY env var)
        task: Task-specific LoRA adapter (optional)
        normalized: Whether to L2-normalize embeddings (default: True)

    Returns:
        List of embedding vectors

    Raises:
        ValueError: If API key is missing
        httpx.HTTPError: If API request fails

    """
    api_key = api_key or os.environ.get("JINA_API_KEY")
    if not api_key:
        msg = "JINA_API_KEY environment variable required for Jina embeddings"
        raise ValueError(msg)

    # Strip quotes from API key (common shell export issue: export KEY="value")
    api_key = api_key.strip('"').strip("'")

    url = "https://api.jina.ai/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": texts,
        "normalized": normalized,
    }

    # Add task if specified
    if task:
        payload["task"] = task

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        # Extract embeddings from response
        # Jina API returns: {"data": [{"embedding": [...]}, ...]}
        return [item["embedding"] for item in data["data"]]
