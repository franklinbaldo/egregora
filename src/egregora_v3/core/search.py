"""Search and Retrieval core types for V3."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RAGHit(BaseModel):
    """Single retrieval result (one chunk).

    Represents a chunk of text retrieved from the RAG knowledge base,
    along with metadata and similarity score.
    """

    document_id: str = Field(..., description="Original document ID")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Chunk text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Merged metadata")
    score: float = Field(..., description="Similarity score (higher = better)")


class RAGQueryRequest(BaseModel):
    """Query parameters for RAG retrieval."""

    text: str = Field(..., description="Query text")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results to retrieve")
    filters: str | None = Field(default=None, description="Optional SQL WHERE clause for filtering")


class RAGQueryResponse(BaseModel):
    """RAG response with ranked hits."""

    hits: list[RAGHit] = Field(default_factory=list, description="Ranked retrieval results")
