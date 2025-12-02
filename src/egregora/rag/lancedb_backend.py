"""LanceDB-based RAG backend.

Provides vector storage and similarity search using LanceDB with native Python.
Uses Arrow for zero-copy data transfer (no Pandas dependency).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import lancedb
import numpy as np
from lancedb.pydantic import LanceModel, Vector

from egregora.config import EMBEDDING_DIM
from egregora.data_primitives.document import Document
from egregora.rag.ingestion import chunks_from_documents
from egregora.rag.models import RAGHit, RAGQueryRequest, RAGQueryResponse

logger = logging.getLogger(__name__)

# Type alias for embedding functions
EmbedFn = Callable[[Sequence[str], str], list[list[float]]]


# Specific exception classes for better error handling
class RagBackendError(RuntimeError):
    """Base exception for RAG backend errors."""


class EmbeddingError(RagBackendError):
    """Raised when embedding generation fails."""


class StorageError(RagBackendError):
    """Raised when storage operations (index/query) fail."""


@dataclass
class RagChunk:
    """Generic data structure for RAG chunks, decoupled from storage implementation."""
    chunk_id: str
    document_id: str
    text: str
    vector: list[float]
    metadata_json: str


class RagChunkModel(LanceModel):
    """Schema for RAG chunks stored in LanceDB.

    Uses LanceDB's Pydantic integration for type-safe schema definition.
    This maps directly to Arrow types without requiring Pandas.
    """

    chunk_id: str
    document_id: str
    text: str
    vector: Vector(EMBEDDING_DIM)  # type: ignore[valid-type]
    metadata_json: str

    @classmethod
    def from_generic(cls, chunk: RagChunk) -> RagChunkModel:
        """Create a LanceDB model from a generic RagChunk."""
        return cls(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            text=chunk.text,
            vector=np.asarray(chunk.vector, dtype=np.float32),
            metadata_json=chunk.metadata_json
        )


class LanceDBRAGBackend:
    """LanceDB-based RAG backend.

    Responsibilities:
        - Convert Documents to chunks using ingestion module
        - Compute embeddings with provided embed_fn
        - Upsert into LanceDB table
        - Run vector search and return RAGHit objects

    """

    def __init__(
        self,
        db_dir: Path,
        table_name: str,
        embed_fn: EmbedFn,
        indexable_types: set[Any] | None = None,
    ) -> None:
        """Initialize LanceDB RAG backend."""
        self._db_dir = db_dir
        self._table_name = table_name
        self._embed_fn = embed_fn
        self._indexable_types = indexable_types

        # Initialize LanceDB connection
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(db_dir))

            # Create or open table using Pydantic schema
            if table_name not in self._db.table_names():
                logger.info("Creating new LanceDB table: %s", table_name)
                self._table = self._db.create_table(
                    table_name,
                    schema=RagChunkModel,
                    mode="overwrite",
                )
            else:
                logger.info("Opening existing LanceDB table: %s", table_name)
                self._table = self._db.open_table(table_name)
        except Exception as e:
            msg = f"Failed to initialize LanceDB at {db_dir}: {e}"
            raise StorageError(msg) from e

    def index_documents(self, docs: Sequence[Document]) -> None:
        """Index a batch of Documents into the RAG knowledge base."""
        # Convert documents to chunks
        chunks = chunks_from_documents(docs, indexable_types=self._indexable_types)

        if not chunks:
            logger.info("No chunks to index (empty or filtered documents)")
            return

        logger.info("Indexing %d chunks from %d documents", len(chunks), len(docs))

        # Extract texts for embedding
        texts = [c.text for c in chunks]

        # Compute embeddings with RETRIEVAL_DOCUMENT task type
        try:
            embeddings = self._embed_fn(texts, "RETRIEVAL_DOCUMENT")
        except Exception as e:
            msg = f"Failed to compute embeddings: {e}"
            raise EmbeddingError(msg) from e

        if len(embeddings) != len(chunks):
            msg = f"Embedding count mismatch: got {len(embeddings)}, expected {len(chunks)}"
            raise EmbeddingError(msg)

        # Prepare generic chunks first, then convert to model
        model_rows: list[RagChunkModel] = []
        for chunk, emb in zip(chunks, embeddings, strict=True):
            generic_chunk = RagChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                text=chunk.text,
                vector=emb,
                metadata_json=json.dumps(chunk.metadata),
            )
            model_rows.append(RagChunkModel.from_generic(generic_chunk))

        # Atomic upsert using merge_insert (no race conditions)
        try:
            self._table.merge_insert(
                "chunk_id"
            ).when_matched_update_all().when_not_matched_insert_all().execute(model_rows)
            logger.info("Successfully indexed %d chunks (atomic upsert)", len(model_rows))
        except Exception as e:
            msg = f"Failed to upsert chunks to LanceDB: {e}"
            raise StorageError(msg) from e

    def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Execute vector search in the knowledge base."""
        top_k = request.top_k

        # Embed query with RETRIEVAL_QUERY task type
        try:
            query_emb = self._embed_fn([request.text], "RETRIEVAL_QUERY")[0]
        except Exception as e:
            msg = f"Failed to embed query: {e}"
            raise EmbeddingError(msg) from e

        query_vec = np.asarray(query_emb, dtype=np.float32)

        # Execute search using Arrow (zero-copy, no Pandas)
        try:
            q = self._table.search(query_vec).metric("cosine").limit(top_k)

            # Apply filters if provided
            if request.filters:
                q = q.where(request.filters)

            # Execute and get results as Arrow table (zero-copy)
            arrow_table = q.to_arrow()
        except Exception as e:
            msg = f"LanceDB search failed: {e}"
            raise StorageError(msg) from e

        # Convert Arrow table to Python dicts (fast native method)
        hits: list[RAGHit] = []
        for row in arrow_table.to_pylist():
            distance = float(row.get("_distance", 0.0))
            score = 1.0 - distance

            metadata_json = row.get("metadata_json", "{}")
            try:
                meta = json.loads(metadata_json) if metadata_json else {}
            except json.JSONDecodeError:
                logger.warning("Failed to decode metadata JSON, using empty dict")
                meta = {}

            hits.append(
                RAGHit(
                    document_id=row["document_id"],
                    chunk_id=row["chunk_id"],
                    text=row["text"],
                    metadata=meta,
                    score=score,
                )
            )

        logger.info("Found %d hits for query (top_k=%d)", len(hits), top_k)
        return RAGQueryResponse(hits=hits)


__all__ = ["EmbedFn", "LanceDBRAGBackend", "RagBackendError", "EmbeddingError", "StorageError"]
