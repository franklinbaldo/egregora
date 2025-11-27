"""LanceDB-based RAG backend.

Provides vector storage and similarity search using LanceDB with native Python.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import lancedb
import numpy as np

from egregora.data_primitives.document import Document

from .backend import RAGBackend
from .ingestion import _RAGChunk, chunks_from_documents
from .models import RAGHit, RAGQueryRequest, RAGQueryResponse

logger = logging.getLogger(__name__)

# Type alias for embedding functions
EmbedFn = Callable[[Sequence[str]], list[list[float]]]


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
        top_k_default: int = 5,
    ) -> None:
        """Initialize LanceDB RAG backend.

        Args:
            db_dir: Directory for LanceDB database
            table_name: Name of the table to store embeddings
            embed_fn: Function that takes texts and returns embeddings
            top_k_default: Default number of results to return (default: 5)

        """
        self._db_dir = db_dir
        self._table_name = table_name
        self._embed_fn = embed_fn
        self._top_k_default = top_k_default

        # Initialize LanceDB connection
        db_dir.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(db_dir))

        # Create or open table
        if table_name not in self._db.table_names():
            logger.info("Creating new LanceDB table: %s", table_name)
            # Initialize with empty schema
            # Store metadata as JSON string to avoid schema conflicts
            self._table = self._db.create_table(
                table_name,
                data=[
                    {
                        "chunk_id": "",
                        "document_id": "",
                        "text": "",
                        "embedding": np.zeros(768, dtype=np.float32),  # Gemini embedding dim
                        "metadata_json": "{}",  # Store as JSON string
                    }
                ],
                mode="overwrite",
            )
            # Delete the placeholder row
            self._table.delete("chunk_id == ''")
        else:
            logger.info("Opening existing LanceDB table: %s", table_name)
            self._table = self._db.open_table(table_name)

    def index_documents(self, docs: Sequence[Document]) -> None:
        """Index a batch of Documents into the RAG knowledge base.

        Implementation:
            1. Convert Documents to chunks using ingestion module
            2. Compute embeddings for all chunk texts
            3. Upsert into LanceDB (delete existing, then add)

        Args:
            docs: Sequence of Document instances to index

        Raises:
            ValueError: If documents are invalid
            RuntimeError: If embedding or storage operations fail

        """
        # Convert documents to chunks
        chunks = chunks_from_documents(docs)

        if not chunks:
            logger.info("No chunks to index (empty or filtered documents)")
            return

        logger.info("Indexing %d chunks from %d documents", len(chunks), len(docs))

        # Extract texts for embedding
        texts = [c.text for c in chunks]

        # Compute embeddings
        try:
            embeddings = self._embed_fn(texts)
        except Exception as e:
            msg = f"Failed to compute embeddings: {e}"
            raise RuntimeError(msg) from e

        if len(embeddings) != len(chunks):
            msg = f"Embedding count mismatch: got {len(embeddings)}, expected {len(chunks)}"
            raise RuntimeError(msg)

        # Prepare rows for LanceDB
        rows: list[dict[str, Any]] = []
        for chunk, emb in zip(chunks, embeddings, strict=True):
            rows.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "embedding": np.asarray(emb, dtype=np.float32),
                    "metadata_json": json.dumps(chunk.metadata),  # Serialize metadata to JSON
                }
            )

        # Upsert: delete existing rows with the same chunk_ids, then add
        chunk_ids = [c.chunk_id for c in chunks]
        if chunk_ids:
            try:
                # Delete existing chunks (LanceDB uses SQL-like syntax)
                # Convert list to tuple for SQL IN clause
                chunk_ids_tuple = tuple(chunk_ids) if len(chunk_ids) > 1 else f"('{chunk_ids[0]}')"
                if len(chunk_ids) == 1:
                    self._table.delete(f"chunk_id = '{chunk_ids[0]}'")
                else:
                    # For multiple IDs, use IN clause
                    ids_str = ", ".join([f"'{cid}'" for cid in chunk_ids])
                    self._table.delete(f"chunk_id IN ({ids_str})")
            except Exception as e:
                logger.warning("Failed to delete existing chunks (may not exist): %s", e)

        # Add new chunks
        try:
            self._table.add(rows)
            logger.info("Successfully indexed %d chunks", len(rows))
        except Exception as e:
            msg = f"Failed to add chunks to LanceDB: {e}"
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
        top_k = request.top_k or self._top_k_default

        # Embed query
        try:
            query_emb = self._embed_fn([request.text])[0]
        except Exception as e:
            msg = f"Failed to embed query: {e}"
            raise RuntimeError(msg) from e

        query_vec = np.asarray(query_emb, dtype=np.float32)

        # Execute search
        try:
            q = self._table.search(query_vec).limit(top_k)

            # Apply filters if provided
            # LanceDB supports SQL-like WHERE clauses
            # For now, we skip complex filters and handle them post-search
            # Future: translate request.filters to WHERE clauses

            # Execute and get results
            df = q.to_pandas()
        except Exception as e:
            msg = f"LanceDB search failed: {e}"
            raise RuntimeError(msg) from e

        # Convert to RAGHit objects
        hits: list[RAGHit] = []
        for _, row in df.iterrows():
            # LanceDB exposes a distance column (usually "_distance")
            distance = float(row.get("_distance", 0.0))

            # Convert distance to similarity score
            # For cosine distance: similarity = 1 - distance
            # (LanceDB uses distance, lower is better; we want similarity, higher is better)
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


__all__ = ["LanceDBRAGBackend", "EmbedFn"]
