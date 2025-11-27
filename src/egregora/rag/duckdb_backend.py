"""DuckDB legacy backend adapter.

Wraps the existing DuckDB VSS-based RAG implementation to implement the
RAGBackend protocol. This provides backward compatibility while we migrate
to the new LanceDB backend.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from egregora.data_primitives.document import Document

from .backend import RAGBackend
from .models import RAGHit, RAGQueryRequest, RAGQueryResponse

logger = logging.getLogger(__name__)


class DuckDBRAGBackend:
    """Adapter over current DuckDB VSS implementation.

    This is a temporary adapter to maintain backward compatibility while
    we migrate to LanceDB. It wraps the existing VectorStore implementation.

    Note:
        This backend is deprecated and will be removed in a future version.
        New code should use LanceDBRAGBackend.

    """

    def __init__(
        self,
        parquet_path: Path,
        storage: Any,  # type: ignore[misc]  # StorageProtocol
        embedding_model: str,
        top_k_default: int = 5,
    ) -> None:
        """Initialize DuckDB legacy backend.

        Args:
            parquet_path: Path to parquet file for vector data
            storage: Storage backend (DuckDBStorageManager)
            embedding_model: Model name for embeddings
            top_k_default: Default number of results to return

        """
        # Lazy import to avoid circular dependency
        from egregora.agents.shared.rag.store import VectorStore

        self._store = VectorStore(parquet_path, storage=storage)
        self._embedding_model = embedding_model
        self._top_k_default = top_k_default

    def index_documents(self, docs: Sequence[Document]) -> None:
        """Index a batch of Documents into the RAG knowledge base.

        Delegates to the existing VectorStore.index_documents() method.

        Args:
            docs: Sequence of Document instances to index

        Raises:
            ValueError: If documents are invalid
            RuntimeError: If embedding or storage operations fail

        """
        from egregora.data_primitives.protocols import OutputAdapter

        # The existing VectorStore.index_documents() expects an OutputAdapter
        # For now, we'll create a simple adapter that wraps our documents

        class _DocumentListAdapter:
            """Minimal adapter to wrap a list of documents."""

            def __init__(self, documents: Sequence[Document]) -> None:
                self._documents = list(documents)

            def documents(self) -> list[Document]:  # type: ignore[misc]
                return self._documents

        adapter = _DocumentListAdapter(docs)

        # Index using the existing VectorStore facade
        indexed_count = self._store.index_documents(adapter, embedding_model=self._embedding_model)  # type: ignore[arg-type]

        logger.info("DuckDB legacy backend indexed %d documents", indexed_count)

    def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Execute vector search in the knowledge base.

        Delegates to VectorStore.embed_query() and VectorStore.search().

        Args:
            request: Query parameters (text, top_k, filters)

        Returns:
            Response containing ranked RAGHit results

        Raises:
            ValueError: If query parameters are invalid
            RuntimeError: If search operation fails

        """
        from egregora.agents.shared.rag.embedder import embed_query_text

        top_k = request.top_k or self._top_k_default

        # Embed the query
        try:
            query_vec = embed_query_text(request.text, model=self._embedding_model)
        except Exception as e:
            msg = f"Failed to embed query: {e}"
            raise RuntimeError(msg) from e

        # Execute search using VectorStore
        try:
            # Build filter params from request.filters
            # The existing VectorStore.search() accepts multiple filter parameters
            document_type = request.filters.get("document_type") if request.filters else None
            media_types = request.filters.get("media_types") if request.filters else None

            results_table = self._store.search(
                query_vec=query_vec,
                top_k=top_k,
                document_type=document_type,
                media_types=media_types,
                mode="ann",  # Use ANN by default
            )
        except Exception as e:
            msg = f"DuckDB search failed: {e}"
            raise RuntimeError(msg) from e

        # Convert Ibis table to RAGHit objects
        hits: list[RAGHit] = []

        try:
            results_df = results_table.execute()

            for _, row in results_df.iterrows():
                # Extract fields from the search result
                hits.append(
                    RAGHit(
                        document_id=row.get("document_id", ""),
                        chunk_id=row.get("chunk_id", ""),
                        text=row.get("content", ""),  # DuckDB stores as 'content'
                        metadata={
                            "post_slug": row.get("post_slug"),
                            "post_title": row.get("post_title"),
                            "post_date": str(row.get("post_date")) if row.get("post_date") else None,
                            "media_type": row.get("media_type"),
                            "document_type": row.get("document_type"),
                            "tags": row.get("tags", []),
                            "authors": row.get("authors", []),
                        },
                        score=float(row.get("similarity", 0.0)),
                    )
                )
        except Exception as e:
            logger.warning("Failed to convert DuckDB results to RAGHit: %s", e)
            # Return empty response on conversion failure
            return RAGQueryResponse(hits=[])

        logger.info("DuckDB legacy backend returned %d hits", len(hits))
        return RAGQueryResponse(hits=hits)


__all__ = ["DuckDBRAGBackend"]
