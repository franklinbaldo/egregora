"""Embedding generation using the google.genai client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from egregora.utils.genai_helpers import embed_batch, embed_text

if TYPE_CHECKING:
    from google import genai

logger = logging.getLogger(__name__)


def embed_chunks(
    chunks: Annotated[list[str], "A list of text chunks to embed"],
    client: Annotated[genai.Client, "The Gemini API client"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    task_type: Annotated[str, "The task type for the embedding model"] = "RETRIEVAL_DOCUMENT",
    output_dimensionality: Annotated[int, "The target dimensionality for the embeddings"] = 3072,
) -> Annotated[list[list[float]], "A list of embedding vectors for the chunks"]:
    """Embed text chunks using the genai client."""
    if not chunks:
        return []

    embeddings = embed_batch(
        client,
        chunks,
        model=model,
        task_type=task_type,
        output_dimensionality=output_dimensionality,
    )

    logger.info(
        "Embedded %d chunks (%d dimensions)",
        len(embeddings),
        output_dimensionality,
    )

    return embeddings


def embed_query(
    query_text: Annotated[str, "The query text to embed"],
    client: Annotated[genai.Client, "The Gemini API client"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    output_dimensionality: Annotated[int, "The target dimensionality for the embedding"] = 3072,
) -> Annotated[list[float], "The embedding vector for the query"]:
    """Embed a single query string for retrieval."""
    return embed_text(
        client,
        query_text,
        model=model,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=output_dimensionality,
    )
