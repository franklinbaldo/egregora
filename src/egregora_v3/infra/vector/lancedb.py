"""LanceDB Vector Store for V3.

Simplified vector storage for semantic search over documents.
Stores full documents (not chunks) with vector embeddings.
"""

import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path

import lancedb
import numpy as np
from lancedb.pydantic import LanceModel, Vector

from egregora_v3.core.types import Author, Category, Document, DocumentStatus, DocumentType, Link

logger = logging.getLogger(__name__)

# Type alias for embedding functions
# task_type should be "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for searching
EmbedFn = Callable[[Sequence[str], str], list[list[float]]]

# Default embedding dimension (adjust based on your model)
EMBEDDING_DIM = 768


# Pydantic schema for LanceDB
class DocumentVectorModel(LanceModel):
    """Schema for documents stored in LanceDB.

    Stores full documents with vector embeddings.
    """

    document_id: str  # Primary key
    vector: Vector(EMBEDDING_DIM)  # type: ignore[valid-type]
    # Serialize full document as JSON for complete roundtrip
    document_json: str


class LanceDBVectorStore:
    """LanceDB-based vector store for V3.

    Simplified implementation that stores full documents (not chunks).
    Supports indexing and semantic search.
    """

    def __init__(
        self,
        db_dir: Path,
        table_name: str,
        embed_fn: EmbedFn,
    ) -> None:
        """Initialize LanceDB vector store.

        Args:
            db_dir: Directory for LanceDB database
            table_name: Name of the table to store vectors
            embed_fn: Function that takes texts and returns embeddings

        """
        self._db_dir = Path(db_dir)
        self._table_name = table_name
        self._embed_fn = embed_fn

        # Initialize LanceDB connection
        self._db_dir.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_dir))

        # Create or open table using Pydantic schema
        if table_name not in self._db.table_names():
            logger.info("Creating new LanceDB table: %s", table_name)
            # Create empty table with schema
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

        Args:
            docs: List of documents to index

        Each document is embedded based on its content and stored with
        its full metadata for retrieval.

        """
        if not docs:
            logger.info("No documents to index")
            return

        logger.info("Indexing %d documents", len(docs))

        # Extract texts for embedding (use title + content)
        texts = [f"{doc.title}\n\n{doc.content or ''}" for doc in docs]

        # Compute embeddings
        try:
            embeddings = self._embed_fn(texts, "RETRIEVAL_DOCUMENT")
        except Exception as e:
            msg = f"Failed to compute embeddings: {e}"
            raise RuntimeError(msg) from e

        if len(embeddings) != len(docs):
            msg = f"Embedding count mismatch: got {len(embeddings)}, expected {len(docs)}"
            raise RuntimeError(msg)

        # Prepare rows using Pydantic models
        rows: list[DocumentVectorModel] = []
        for doc, emb in zip(docs, embeddings, strict=True):
            # Serialize document to JSON for storage
            doc_json = doc.model_dump_json()

            rows.append(
                DocumentVectorModel(
                    document_id=doc.id,
                    vector=np.asarray(emb, dtype=np.float32),
                    document_json=doc_json,
                )
            )

        # Upsert documents (update if exists, insert if not)
        try:
            # Use merge_insert for atomic upsert
            self._table.merge_insert(
                "document_id"
            ).when_matched_update_all().when_not_matched_insert_all().execute(rows)
            logger.info("Successfully indexed %d documents", len(rows))
        except Exception as e:
            msg = f"Failed to upsert documents to LanceDB: {e}"
            raise RuntimeError(msg) from e

    def search(self, query: str, top_k: int = 5) -> list[Document]:
        """Search for documents using semantic similarity.

        Args:
            query: Search query text
            top_k: Maximum number of results to return

        Returns:
            List of Document objects ranked by relevance

        """
        # Check if table is empty
        try:
            # Try to count rows - if table doesn't exist or is empty, return empty list
            if self._table_name not in self._db.table_names():
                return []

            # Quick check for empty table
            arrow_table = self._table.search().limit(1).to_arrow()
            if len(arrow_table) == 0:
                return []
        except Exception:  # noqa: BLE001
            # Table might not exist yet
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

        # Convert Arrow table to Documents
        documents: list[Document] = []
        for row in arrow_table.to_pylist():
            # Deserialize document from JSON
            doc_json = row.get("document_json", "{}")
            try:
                doc_dict = json.loads(doc_json)
                # Reconstruct Document from dict
                doc = self._reconstruct_document(doc_dict)
                documents.append(doc)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Failed to deserialize document %s: %s",
                    row.get("document_id", "unknown"),
                    e,
                )
                continue

        logger.info("Found %d documents for query (top_k=%d)", len(documents), top_k)
        return documents

    def _reconstruct_document(self, doc_dict: dict) -> Document:
        """Reconstruct a Document from a dictionary.

        Args:
            doc_dict: Dictionary containing document data

        Returns:
            Reconstructed Document object

        """
        # Convert enum strings back to enums
        if "doc_type" in doc_dict:
            doc_dict["doc_type"] = DocumentType(doc_dict["doc_type"])
        if "status" in doc_dict:
            doc_dict["status"] = DocumentStatus(doc_dict["status"])

        # Convert nested objects
        if doc_dict.get("authors"):
            doc_dict["authors"] = [Author(**a) for a in doc_dict["authors"]]
        if doc_dict.get("categories"):
            doc_dict["categories"] = [Category(**c) for c in doc_dict["categories"]]
        if doc_dict.get("links"):
            doc_dict["links"] = [Link(**link) for link in doc_dict["links"]]

        return Document(**doc_dict)
