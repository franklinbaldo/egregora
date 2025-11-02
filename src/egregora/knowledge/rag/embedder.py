"""Embedding generation using the Gemini Batch API."""

from __future__ import annotations

import logging

from egregora.utils.batch import EmbeddingBatchRequest, GeminiBatchClient

logger = logging.getLogger(__name__)


def embed_chunks(
    chunks: list[str],
    batch_client: GeminiBatchClient,
    *,
    model: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int = 3072,
    batch_size: int = 100,
) -> list[list[float]]:
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
    query_text: str,
    batch_client: GeminiBatchClient,
    *,
    model: str,
    output_dimensionality: int = 3072,
) -> list[float]:
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
