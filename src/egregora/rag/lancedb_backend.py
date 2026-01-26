"""LanceDB-based RAG backend.

Provides vector storage and similarity search using LanceDB with native Python.
Uses Arrow for zero-copy data transfer (no Pandas dependency).
"""

import json
import logging
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import lancedb
import numpy as np
from lancedb.pydantic import LanceModel, Vector

from egregora.config import EMBEDDING_DIM
from egregora.rag.backend import VectorStore
from egregora.rag.ingestion import chunks_from_documents
from egregora.rag.models import RAGHit, RAGQueryRequest, RAGQueryResponse

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document

logger = logging.getLogger(__name__)


def _json_serialize_metadata(metadata: dict) -> str:
    """Serialize metadata dict to JSON, converting datetime objects to ISO format.

    Args:
        metadata: Dictionary that may contain datetime objects

    Returns:
        JSON string with datetime objects converted to ISO format strings

    """

    def default_serializer(obj: Any) -> str:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        msg = f"Object of type {type(obj).__name__} is not JSON serializable"
        raise TypeError(msg)

    return json.dumps(metadata, default=default_serializer)


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
    vector: Vector(EMBEDDING_DIM)
    metadata_json: str  # JSON-serialized metadata for flexibility


class LanceDBRAGBackend(VectorStore):
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
        # Use exist_ok=True to handle race conditions in parallel test execution
        try:
            if table_name not in self._db.list_tables():
                logger.info("Creating new LanceDB table: %s", table_name)
                # Use Pydantic schema for type-safe table creation
                self._table = self._db.create_table(
                    table_name,
                    schema=RagChunkModel,
                    mode="create",
                    exist_ok=True,
                )
            else:
                logger.info("Opening existing LanceDB table: %s", table_name)
                self._table = self._db.open_table(table_name)
        except Exception as e:
            # If table creation fails (e.g., race condition), try to open existing table
            logger.warning("Table creation failed, attempting to open existing table: %s", e)
            try:
                self._table = self._db.open_table(table_name)
            except Exception as open_err:
                msg = f"Failed to create or open table {table_name}: {open_err}"
                raise RuntimeError(msg) from open_err

    def add(self, documents: Sequence["Document"]) -> int:
        """Add documents to the store.

        Implementation:
            1. Convert Documents to chunks using ingestion module
            2. Compute embeddings for all chunk texts
            3. Atomic upsert into LanceDB (merge_insert with update/insert)

        Args:
            documents: Sequence of Document instances to index

        Returns:
            Number of documents successfully indexed

        Raises:
            ValueError: If documents are invalid
            RuntimeError: If embedding or storage operations fail

        """
        # Convert documents to chunks
        chunks = chunks_from_documents(documents, indexable_types=self._indexable_types)

        if not chunks:
            logger.info("No chunks to index (empty or filtered documents)")
            return 0

        logger.info("Indexing %d chunks from %d documents", len(chunks), len(documents))

        # Extract texts for embedding
        texts = [c.text for c in chunks]

        # Compute embeddings with RETRIEVAL_DOCUMENT task type
        try:
            embeddings = self._embed_fn(tuple(texts), "RETRIEVAL_DOCUMENT")
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
                    metadata_json=_json_serialize_metadata(chunk.metadata),
                )
            )

        # Atomic upsert using merge_insert (no race conditions)
        try:
            self._table.merge_insert(
                "chunk_id"
            ).when_matched_update_all().when_not_matched_insert_all().execute(rows)
            logger.info("Successfully indexed %d chunks (atomic upsert)", len(rows))
            return len(documents)
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
            query_emb = self._embed_fn((request.text,), "RETRIEVAL_QUERY")[0]
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
        hits: list[RAGHit] = []
        for row in arrow_table.to_pylist():
            # LanceDB exposes a distance column (usually "_distance")
            distance = float(row.get("_distance", 0.0))

            # Convert distance to similarity score
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

    def delete(self, document_ids: list[str]) -> int:
        """Delete documents from the store.

        Args:
            document_ids: List of document IDs to delete

        Returns:
            Number of documents deleted

        """
        if not document_ids:
            return 0

        # Construct filter expression: document_id IN ('id1', 'id2')
        # LanceDB SQL filter syntax
        ids_str = ", ".join(f"'{did}'" for did in document_ids)
        filter_expr = f"document_id IN ({ids_str})"

        try:
            self._table.delete(filter_expr)
            # LanceDB delete doesn't return count easily without another query
            # We assume success if no exception
            return len(document_ids)
        except Exception as e:
            logger.exception("Failed to delete documents: %s", e)
            msg = f"Delete failed: {e}"
            raise RuntimeError(msg) from e

    def count(self) -> int:
        """Count total documents in the store.

        Note: This counts chunks, not unique documents.
        """
        return self._table.count_rows()

    def get_all_post_vectors(self) -> tuple[list[str], np.ndarray]:
        """Retrieve IDs and Centroid Vectors for all indexed posts.

        Returns:
            (doc_ids, vectors_matrix)

        """
        # Fetch all vectors (Zero-copy Arrow)
        # In a real scenario, filter by "document_type" metadata if possible
        arrow_table = self._table.search().limit(None).to_arrow()

        doc_vectors: dict[str, list[np.ndarray]] = {}

        # Aggregate chunks by document ID
        for batch in arrow_table.to_batches():
            d = batch.to_pydict()
            ids = d["document_id"]
            vecs = d["vector"]
            # Assume we only process POSTs based on upstream logic or metadata checks

            for i, doc_id in enumerate(ids):
                if doc_id not in doc_vectors:
                    doc_vectors[doc_id] = []
                doc_vectors[doc_id].append(vecs[i])

        if not doc_vectors:
            return [], np.array([])

        # Compute centroids (Mean of chunk vectors)
        final_ids = []
        final_vecs = []

        for doc_id, vec_list in doc_vectors.items():
            centroid = np.mean(np.stack(vec_list), axis=0)
            final_ids.append(doc_id)
            final_vecs.append(centroid)

        return final_ids, np.array(final_vecs)


__all__ = ["EmbedFn", "LanceDBRAGBackend"]
