"""Embedding generation using Google Generative AI HTTP API."""

from __future__ import annotations

import logging
from typing import Annotated

from egregora.utils.genai_helpers import embed_batch, embed_text

logger = logging.getLogger(__name__)


def embed_chunks(
    chunks: Annotated[list[str], "A list of text chunks to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    task_type: Annotated[str, "The task type for the embedding model"] = "RETRIEVAL_DOCUMENT",
    output_dimensionality: Annotated[int, "The target dimensionality for the embeddings"] = 3072,
) -> Annotated[list[list[float]], "A list of embedding vectors for the chunks"]:
    """Embed text chunks using the Google Generative AI HTTP API."""
    if not chunks:
        return []

    embeddings = embed_batch(
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
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    output_dimensionality: Annotated[int, "The target dimensionality for the embedding"] = 3072,
) -> Annotated[list[float], "The embedding vector for the query"]:
    """Embed a single query string for retrieval."""
    return embed_text(
        query_text,
        model=model,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=output_dimensionality,
    )
