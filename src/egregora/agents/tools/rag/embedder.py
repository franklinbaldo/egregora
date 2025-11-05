"""Embedding generation using the Gemini Batch API."""

from __future__ import annotations

import logging
from typing import Annotated

from egregora.agents.utils.batch import EmbeddingBatchRequest, GeminiBatchClient

logger = logging.getLogger(__name__)


def embed_chunks(
    chunks: Annotated[list[str], "A list of text chunks to embed"],
    batch_client: Annotated[GeminiBatchClient, "The batch Gemini client for embeddings"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    task_type: Annotated[str, "The task type for the embedding model"] = "RETRIEVAL_DOCUMENT",
    output_dimensionality: Annotated[int, "The target dimensionality for the embeddings"] = 3072,
    batch_size: Annotated[int, "The number of chunks to process in each batch"] = 100,
) -> Annotated[list[list[float]], "A list of embedding vectors for the chunks"]:
    """Embed text chunks using a single batch job per group."""
    if not chunks:
        return []

    embeddings: list[list[float]] = []

    logger.info("[blue]📚 Embedding model:[/] %s — %d chunk(s)", model, len(chunks))

    for index in range(0, len(chunks), batch_size):
        batch = chunks[index : index + batch_size]
        requests = [
            EmbeddingBatchRequest(
                text=text,
                tag=str(index + offset),
                model=model,
                task_type=task_type,
                output_dimensionality=output_dimensionality,
            )
            for offset, text in enumerate(batch)
        ]

        results = batch_client.embed_content(
            requests,
            display_name="Egregora Embedding Batch",
        )

        for request, result in zip(requests, results, strict=False):
            if result.embedding is None:
                raise RuntimeError(f"Embedding failed for chunk index {request.tag}")
            embeddings.append(result.embedding)

    logger.info(
        "Embedded %d chunks (%d dimensions)",
        len(embeddings),
        output_dimensionality,
    )

    return embeddings


def embed_query(
    query_text: Annotated[str, "The query text to embed"],
    batch_client: Annotated[GeminiBatchClient, "The batch Gemini client for embeddings"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    output_dimensionality: Annotated[int, "The target dimensionality for the embedding"] = 3072,
) -> Annotated[list[float], "The embedding vector for the query"]:
    """Embed a single query string for retrieval."""
    requests = [
        EmbeddingBatchRequest(
            text=query_text,
            tag="query",
            model=model,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=output_dimensionality,
        )
    ]

    results = batch_client.embed_content(
        requests,
        display_name="Egregora Query Embedding",
    )

    if not results or results[0].embedding is None:
        raise RuntimeError("Failed to embed query text")

    return results[0].embedding
