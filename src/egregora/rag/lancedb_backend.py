"""LanceDB-based RAG backend.

Provides vector storage and similarity search using LanceDB with native Python.
Uses Arrow for zero-copy data transfer (no Pandas dependency).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
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
# task_type should be "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for searching
EmbedFn = Callable[[Sequence[str], str], list[list[float]]]


# Pydantic-based schema for LanceDB (zero-copy Arrow)
class RagChunkModel(LanceModel):
    """Schema for RAG chunks stored in LanceDB.

    Uses LanceDB's Pydantic integration for type-safe schema definition.
    This maps directly to Arrow types without requiring Pandas.
    """

    chunk_id: str
    document_id: str
    text: str
    vector: Vector(EMBEDDING_DIM)  # type: ignore[valid-type]
    metadata_json: str  # JSON-serialized metadata for flexibility


class LanceDBRAGBackend:
    """LanceDB-based RAG backend.

    Responsibilities:
        - Convert Documents to chunks using ingestion module
        - Compute embeddings with provided embed_fn
        - Upsert into LanceDB table
        - Run vector search and return RAGHit objects

    Architecture:
        - Uses LanceDB for vector storage and search
        - Stores chunks with embeddings, metadata, and full-text
        - Supports both ANN and exact similarity search
        - Dependency injection for embedding function (no direct Gemini coupling)

    Schema:
        - chunk_id: string (primary key)
        - document_id: string
        - text: string
        - embedding: vector<float> (LanceDB vector column)
        - metadata: struct/map (json-like)

    """

    def __init__(
        self,
        db_dir: Path,
        table_name: str,
        embed_fn: EmbedFn,
        indexable_types: set[Any] | None = None,
    ) -> None:
        """Initialize LanceDB RAG backend.

        Args:
            db_dir: Directory for LanceDB database
            table_name: Name of the table to store embeddings
            embed_fn: Function that takes texts and returns embeddings
            indexable_types: Set of DocumentType values to index (optional)

        """
        self._db_dir = db_dir
        self._table_name = table_name
        self._embed_fn = embed_fn
        self._indexable_types = indexable_types

        # Initialize LanceDB connection
        db_dir.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(db_dir))

        # Create or open table using Pydantic schema
        if table_name not in self._db.table_names():
            logger.info("Creating new LanceDB table: %s", table_name)
            # Use Pydantic schema for type-safe table creation
            self._table = self._db.create_table(
                table_name,
                schema=RagChunkModel,
                mode="overwrite",
            )
        else:
            logger.info("Opening existing LanceDB table: %s", table_name)
            self._table = self._db.open_table(table_name)

    def index_documents(self, docs: Sequence[Document]) -> None:
        """Index a batch of Documents into the RAG knowledge base.

        Implementation:
            1. Convert Documents to chunks using ingestion module
            2. Compute embeddings for all chunk texts
            3. Atomic upsert into LanceDB (merge_insert with update/insert)

        Args:
            docs: Sequence of Document instances to index

        Raises:
            ValueError: If documents are invalid
            RuntimeError: If embedding or storage operations fail

        """
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
            raise RuntimeError(msg) from e

        if len(embeddings) != len(chunks):
            msg = f"Embedding count mismatch: got {len(embeddings)}, expected {len(chunks)}"
            raise RuntimeError(msg)

        # Prepare rows using Pydantic models (ensures schema consistency)
        rows: list[RagChunkModel] = []
        for chunk, emb in zip(chunks, embeddings, strict=True):
            rows.append(
                RagChunkModel(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    vector=np.asarray(emb, dtype=np.float32),
                    metadata_json=json.dumps(chunk.metadata),
                )
            )

        # Atomic upsert using merge_insert (no race conditions)
        try:
            self._table.merge_insert(
                "chunk_id"
            ).when_matched_update_all().when_not_matched_insert_all().execute(rows)
            logger.info("Successfully indexed %d chunks (atomic upsert)", len(rows))
        except Exception as e:
            msg = f"Failed to upsert chunks to LanceDB: {e}"
            raise RuntimeError(msg) from e

    def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Execute vector search in the knowledge base.

        Implementation:
            1. Embed the query text
            2. Run vector search in LanceDB
            3. Convert results to RAGHit objects

        Args:
            request: Query parameters (text, top_k, filters)

        Returns:
            Response containing ranked RAGHit results

        Raises:
            ValueError: If query parameters are invalid
            RuntimeError: If search operation fails

        """
        top_k = request.top_k

        # Embed query with RETRIEVAL_QUERY task type
        try:
            query_emb = self._embed_fn([request.text], "RETRIEVAL_QUERY")[0]
        except Exception as e:
            msg = f"Failed to embed query: {e}"
            raise RuntimeError(msg) from e

        query_vec = np.asarray(query_emb, dtype=np.float32)

        # Execute search using Arrow (zero-copy, no Pandas)
        try:
            q = self._table.search(query_vec).metric("cosine").limit(top_k)

            # Apply filters if provided
            # LanceDB supports SQL-like WHERE clauses for pre-filtering
            if request.filters:
                q = q.where(request.filters)

            # Execute and get results as Arrow table (zero-copy)
            arrow_table = q.to_arrow()
        except Exception as e:
            msg = f"LanceDB search failed: {e}"
            raise RuntimeError(msg) from e

        # Convert Arrow table to Python dicts (fast native method)
        # This is much faster than iterating over pandas rows
        hits: list[RAGHit] = []
        for row in arrow_table.to_pylist():
            # LanceDB exposes a distance column (usually "_distance")
            distance = float(row.get("_distance", 0.0))

            # Convert distance to similarity score
            # For cosine distance: distance ∈ [0, 2], similarity = 1 - distance ∈ [-1, 1]
            # Normalize to [0, 1] range: score = (1 - distance) / 2 + 0.5
            # Simplified: score = (2 - distance) / 2 = 1 - (distance / 2)
            # However, for typical use cases, distance should be in [0, 2] range
            # and we want higher similarity scores for lower distances
            score = 1.0 - distance

            # Extract and deserialize metadata
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


__all__ = ["EmbedFn", "LanceDBRAGBackend"]
