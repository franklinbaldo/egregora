"""Simple helpers for embeddings using google.genai client.

This module provides straightforward functions for embeddings operations.
These are utility functions, not agents - they don't need the full pydantic-ai
agent infrastructure since they're simple vector calculations.

For content generation and enrichment, use pydantic-ai agents instead.
"""

from __future__ import annotations

import logging
from typing import Annotated

from google import genai
from google.genai import types as genai_types

from egregora.utils.genai import call_with_retries_sync

logger = logging.getLogger(__name__)


def embed_text(
    client: Annotated[genai.Client, "The Gemini API client"],
    text: Annotated[str, "The text to embed"],
    *,
    model: Annotated[str, "The embedding model to use"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    output_dimensionality: Annotated[int | None, "The output dimensionality"] = None,
) -> Annotated[list[float], "The embedding vector"]:
    """Embed a single text using the genai client.

    Args:
        client: Gemini API client
        text: Text to embed
        model: Embedding model name (e.g., "models/text-embedding-004")
        task_type: Optional task type (e.g., "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY")
        output_dimensionality: Optional output dimensionality (e.g., 768, 3072)

    Returns:
        List of floats representing the embedding vector

    Raises:
        RuntimeError: If embedding fails
    """
    # Build config if needed
    config = None
    if task_type or output_dimensionality:
        config = genai_types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=output_dimensionality,
        )

    try:
        response = call_with_retries_sync(
            client.models.embed_content,
            model=model,
            contents=text,
            config=config,
        )

        # Extract embedding from response
        embedding = getattr(response, "embedding", None)
        values = getattr(embedding, "values", None) if embedding else None

        if values is None:
            raise RuntimeError(f"No embedding returned for text: {text[:50]}...")

        return list(values)

    except Exception as e:
        logger.error("Failed to embed text: %s", e, exc_info=True)
        raise RuntimeError(f"Embedding failed: {e}") from e


def embed_batch(
    client: Annotated[genai.Client, "The Gemini API client"],
    texts: Annotated[list[str], "List of texts to embed"],
    *,
    model: Annotated[str, "The embedding model to use"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    output_dimensionality: Annotated[int | None, "The output dimensionality"] = None,
) -> Annotated[list[list[float]], "List of embedding vectors"]:
    """Embed multiple texts using the batch embeddings API.

    This uses the Gemini batch_embed_contents API for efficient parallel processing.

    Args:
        client: Gemini API client
        texts: List of texts to embed
        model: Embedding model name
        task_type: Optional task type
        output_dimensionality: Optional output dimensionality

    Returns:
        List of embedding vectors

    Raises:
        RuntimeError: If any embedding fails
    """
    if not texts:
        return []

    logger.info("[blue]📚 Embedding model:[/] %s — %d text(s)", model, len(texts))

    # Build config if needed
    config = None
    if task_type or output_dimensionality:
        config = genai_types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=output_dimensionality,
        )

    try:
        # Use batch_embed_contents for efficient parallel processing
        response = call_with_retries_sync(
            client.models.batch_embed_contents,
            model=model,
            requests=[genai_types.EmbedContentRequest(content=text, config=config) for text in texts],
        )

        # Extract embeddings from batch response
        embeddings: list[list[float]] = []
        for i, embedding_result in enumerate(response.embeddings):
            values = getattr(embedding_result, "values", None)
            if values is None:
                logger.error("No embedding returned for text %d/%d", i + 1, len(texts))
                raise RuntimeError(f"No embedding returned for text {i}: {texts[i][:50]}...")
            embeddings.append(list(values))

        logger.info("Embedded %d text(s)", len(embeddings))
        return embeddings

    except Exception as e:
        logger.error("Failed to batch embed texts: %s", e, exc_info=True)
        raise RuntimeError(f"Batch embedding failed: {e}") from e
