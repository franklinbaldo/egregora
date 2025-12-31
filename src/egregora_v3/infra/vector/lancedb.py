"""LanceDB Vector Store for V3.

Simplified vector storage for semantic search over documents.
Stores chunks with vector embeddings.
"""

import json
import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import lancedb
import numpy as np

from egregora_v3.core.ingestion import chunks_from_documents

try:
    from lancedb.pydantic import LanceModel, Vector
except ImportError:
    # `pydantic<2` is used by `mkdocstrings` and is not compatible with `lancedb`.
    # This is a workaround to allow the documentation to build.
    LanceModel = object
    Vector = object
from egregora_v3.core.types import (
    Author,
    Category,
    Document,
    DocumentStatus,
    DocumentType,
    Link,
)

logger = logging.getLogger(__name__)

# Type alias for embedding functions
EmbedFn = Callable[[Sequence[str], str], list[list[float]]]

# Default embedding dimension
EMBEDDING_DIM = 768


# Pydantic schema for LanceDB
class DocumentVectorModel(LanceModel):
    """Schema for document chunks stored in LanceDB."""

    chunk_id: str  # Primary key (doc_id:index)
    document_id: str
    vector: Vector(EMBEDDING_DIM)  # type: ignore[valid-type]
    text: str
    metadata_json: str  # Metadata including original doc info


class LanceDBVectorStore:
    """LanceDB-based vector store for V3.

    Stores document chunks for fine-grained retrieval.
    """

    def __init__(
        self,
        db_dir: Path,
        table_name: str,
        embed_fn: EmbedFn,
    ) -> None:
        """Initialize LanceDB vector store."""
        self._db_dir = Path(db_dir)
        self._table_name = table_name
        self._embed_fn = embed_fn

        # Initialize LanceDB connection
        self._db_dir.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_dir))

        # Create or open table using Pydantic schema
        if table_name not in self._db.table_names():
            logger.info("Creating new LanceDB table: %s", table_name)
            self._table = self._db.create_table(
                table_name,
                schema=DocumentVectorModel,
                mode="overwrite",
            )
        else:
            logger.info("Opening existing LanceDB table: %s", table_name)
            self._table = self._db.open_table(table_name)

    def index_documents(self, docs: list[Document]) -> None:
        """Index documents into the vector store.

        Chunks documents and embeds each chunk.
        """
        if not docs:
            logger.info("No documents to index")
            return

        # Chunk the documents
        chunks = chunks_from_documents(docs)
        if not chunks:
            logger.info("No chunks generated from documents")
            return

        logger.info("Indexing %d chunks from %d documents", len(chunks), len(docs))

        # Extract texts for embedding
        texts = [chunk.text for chunk in chunks]

        # Compute embeddings
        try:
            embeddings = self._embed_fn(texts, "RETRIEVAL_DOCUMENT")
        except Exception as e:
            msg = f"Failed to compute embeddings: {e}"
            raise RuntimeError(msg) from e

        if len(embeddings) != len(chunks):
            msg = f"Embedding count mismatch: got {len(embeddings)}, expected {len(chunks)}"
            raise RuntimeError(msg)

        # Prepare rows using Pydantic models
        rows: list[DocumentVectorModel] = []
        for chunk, emb in zip(chunks, embeddings, strict=True):
            rows.append(
                DocumentVectorModel(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    vector=np.asarray(emb, dtype=np.float32),
                    text=chunk.text,
                    metadata_json=json.dumps(chunk.metadata),
                )
            )

        # Upsert documents (update if exists, insert if not)
        try:
            self._table.merge_insert(
                "chunk_id"
            ).when_matched_update_all().when_not_matched_insert_all().execute(rows)
            logger.info("Successfully indexed %d chunks", len(rows))
        except Exception as e:
            msg = f"Failed to upsert chunks to LanceDB: {e}"
            raise RuntimeError(msg) from e

    def _reconstruct_document_from_chunk(self, chunk_data: dict[str, Any]) -> Document:
        """Reconstructs a Document from a search result chunk."""
        metadata = json.loads(chunk_data["metadata_json"])

        # Reconstruct the document from the chunk's metadata.
        # The content of the document is the chunk's text.
        try:
            doc = Document.model_validate(
                {
                    "id": chunk_data["document_id"],
                    "content": chunk_data["text"],
                    **metadata,
                }
            )
            return doc
        except Exception as e:
            logger.error(
                "Failed to reconstruct document from chunk %s. Metadata: %s, Error: %s",
                chunk_data.get("chunk_id"),
                metadata,
                e,
            )
            # Re-raise to ensure test failures are clear
            raise

    def search(self, query: str, top_k: int = 5) -> list[Document]:
        """Search for documents using semantic similarity.

        Returns:
            List of Document objects reconstructed from the most relevant chunks.
        """
        # Check if table is empty
        try:
            if self._table_name not in self._db.table_names():
                return []
            if len(self._table.search().limit(1).to_arrow()) == 0:
                return []
        except Exception:  # noqa: BLE001
            return []

        # Embed query
        try:
            query_emb = self._embed_fn([query], "RETRIEVAL_QUERY")[0]
        except Exception as e:
            msg = f"Failed to embed query: {e}"
            raise RuntimeError(msg) from e

        query_vec = np.asarray(query_emb, dtype=np.float32)

        # Execute search
        try:
            q = self._table.search(query_vec).metric("cosine").limit(top_k)
            arrow_table = q.to_arrow()
        except Exception as e:
            msg = f"LanceDB search failed: {e}"
            raise RuntimeError(msg) from e

        # Reconstruct documents from chunks. This approach returns one Document
        # per relevant chunk. If multiple chunks from the same document are in
        # top_k, that document may appear multiple times with different content.
        documents: list[Document] = []
        for row in arrow_table.to_pylist():
            try:
                doc = self._reconstruct_document_from_chunk(row)
                documents.append(doc)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(
                    "Failed to reconstruct document from chunk %s: %s",
                    row.get("chunk_id"),
                    e,
                )
                continue

        return documents
