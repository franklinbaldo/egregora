"""Embedding generation using Gemini."""

import logging

from google import genai
from google.genai.types import EmbedContentConfig

logger = logging.getLogger(__name__)


async def embed_chunks(
    chunks: list[str],
    client: genai.Client,
    task_type: str = "RETRIEVAL_DOCUMENT",
    output_dim: int = 3072,
) -> list[list[float]]:
    """
    Embed text chunks using gemini-embedding-001.

    Uses batching (max 100 per batch) for efficiency.

    Args:
        chunks: List of text chunks to embed
        client: Gemini client
        task_type: "RETRIEVAL_DOCUMENT" for indexing or "RETRIEVAL_QUERY" for search
        output_dim: 3072 (default/full quality) or 768 (efficient)

    Returns:
        List of embedding vectors (each 3072-dimensional by default)

    Notes:
        - Model: gemini-embedding-001
        - Max input: 2048 tokens per chunk
        - Batch size: 100 chunks per API call
        - Task type optimizes embeddings for document vs query
    """
    if not chunks:
        return []

    all_embeddings = []

    embedding_model = "gemini-embedding-001"
    logger.info("[blue]📚 Embedding model:[/] %s", embedding_model)

    # Process in batches of 100 (API limit)
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]

        logger.debug(f"Embedding batch {i // batch_size + 1} ({len(batch)} chunks)")

        result = await client.aio.models.embed_content(
            model=embedding_model,
            contents=batch,
            config=EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=output_dim,
            ),
        )

        # Extract embedding values
        for embedding in result.embeddings:
            all_embeddings.append(embedding.values)

    logger.info(f"Embedded {len(chunks)} chunks ({output_dim} dimensions)")

    return all_embeddings


async def embed_query(
    query_text: str,
    client: genai.Client,
    output_dim: int = 3072,
) -> list[float]:
    """
    Embed a query text using RETRIEVAL_QUERY task type.

    Args:
        query_text: Query text to embed
        client: Gemini client
        output_dim: Embedding dimensions (default 3072)

    Returns:
        Embedding vector
    """
    embeddings = await embed_chunks(
        [query_text],
        client,
        task_type="RETRIEVAL_QUERY",
        output_dim=output_dim,
    )

    return embeddings[0]
