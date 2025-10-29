from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class Document(BaseModel):
    """
    A generic representation of a document to be processed and chunked.
    """
    id: str
    content: str
    source: str
    metadata: dict = Field(default_factory=dict)

class RagChunk(BaseModel):
    """
    A single chunk of text ready to be embedded and stored.
    """
    chunk_id: str
    slug: str
    text: str
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QueryHit(BaseModel):
    """
    Represents a single result from a RAG query.
    """
    chunk: RagChunk
    similarity: float

class HealthReport(BaseModel):
    """
    A report on the health of the Egregora v3 system.
    """
    db_reachable: bool
    rag_chunks_count: int
    rag_vectors_count: int
    index_present: bool
    embedding_dimension: int
    anonymization_checksum: str
