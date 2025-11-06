"""Embedding generation using Google Generative AI HTTP API.

All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
"""

from __future__ import annotations

import logging
from typing import Annotated

from egregora.config import EMBEDDING_DIM
from egregora.utils.genai_helpers import embed_batch, embed_text

logger = logging.getLogger(__name__)


def embed_chunks(
    chunks: Annotated[list[str], "A list of text chunks to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    task_type: Annotated[str, "The task type for the embedding model"] = "RETRIEVAL_DOCUMENT",
) -> Annotated[list[list[float]], "A list of 768-dimensional embedding vectors for the chunks"]:
    """Embed text chunks using the Google Generative AI HTTP API.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
    """
    if not chunks:
        return []
    embeddings = embed_batch(chunks, model=model, task_type=task_type)
    logger.info("Embedded %d chunks (%d dimensions)", len(embeddings), EMBEDDING_DIM)
    return embeddings


def embed_query(
    query_text: Annotated[str, "The query text to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
) -> Annotated[list[float], "The 768-dimensional embedding vector for the query"]:
    """Embed a single query string for retrieval.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
    """
    return embed_text(query_text, model=model, task_type="RETRIEVAL_QUERY")
