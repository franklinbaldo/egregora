"""RAG data models.

These are RAG-only types that capture what retrieval needs without leaking
storage implementation details.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RAGHit(BaseModel):
    """Single retrieval result (one chunk).

    Represents a chunk of text retrieved from the RAG knowledge base,
    along with metadata and similarity score.

    Attributes:
        document_id: Original Document.document_id that this chunk belongs to
        chunk_id: ID of the specific chunk (e.g. "{document_id}:{i}")
        text: Chunk text content
        metadata: Merged document and chunk metadata
        score: Similarity score (higher = better, cosine similarity: 0.0-1.0)

    """

    document_id: str = Field(..., description="Original document ID")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Chunk text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Merged metadata")
    score: float = Field(..., description="Similarity score (higher = better)")


class RAGQueryRequest(BaseModel):
    """Query parameters for RAG retrieval.

    Attributes:
        text: Query text to search for
        top_k: Number of top results to retrieve (default: 5)
        filters: Optional SQL WHERE clause for filtering (e.g., "category = 'programming'")

    """

    text: str = Field(..., description="Query text")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results to retrieve")
    filters: str | None = Field(default=None, description="Optional SQL WHERE clause for filtering")


class RAGQueryResponse(BaseModel):
    """RAG response with ranked hits.

    Attributes:
        hits: List of retrieved chunks, ranked by similarity

    """

    hits: list[RAGHit] = Field(default_factory=list, description="Ranked retrieval results")


__all__ = [
    "RAGHit",
    "RAGQueryRequest",
    "RAGQueryResponse",
]
