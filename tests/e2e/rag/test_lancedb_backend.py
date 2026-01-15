"""E2E tests for the LanceDB RAG backend."""
from __future__ import annotations

import uuid
from datetime import datetime

import numpy as np
import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.rag.lancedb_backend import LanceDBRAGBackend
from egregora.rag.models import RAGQueryRequest

from egregora.config import EMBEDDING_DIM

# A mock embedding function for testing
def mock_embed_fn(texts: tuple[str, ...], task_type: str) -> list[list[float]]:
    """Generates deterministic embeddings based on the hash of the text."""
    # This ensures that the same text always gets the same embedding
    embeddings = [
        np.random.default_rng(hash(text) & 0xFFFFFFFF).random(EMBEDDING_DIM)
        for text in texts
    ]
    # Normalize the vectors to ensure the cosine distance is between 0 and 1
    return [list(e / np.linalg.norm(e)) for e in embeddings]


@pytest.fixture
def lancedb_backend(tmp_path):
    """Fixture for a LanceDBRAGBackend instance."""
    db_dir = tmp_path / "lancedb"
    return LanceDBRAGBackend(
        db_dir=db_dir,
        table_name="test_rag",
        embed_fn=mock_embed_fn,
        indexable_types={DocumentType.POST},
    )


@pytest.fixture
def sample_documents() -> list[Document]:
    """Fixture for a list of sample documents."""
    return [
        Document(
            id="doc1",
            content="The quick brown fox jumps over the lazy dog.",
            type=DocumentType.POST,
            metadata={"timestamp": datetime.now()},
        ),
        Document(
            id="doc2",
            content="A journey of a thousand miles begins with a single step.",
            type=DocumentType.POST,
            metadata={"timestamp": datetime.now()},
        ),
    ]


def test_add_and_count_documents(lancedb_backend: LanceDBRAGBackend, sample_documents: list[Document]):
    """Test adding documents to the backend and counting them."""
    assert lancedb_backend.count() == 0

    indexed_count = lancedb_backend.add(sample_documents)
    assert indexed_count == len(sample_documents)

    # Since each document might be split into chunks, we expect at least one.
    assert lancedb_backend.count() > 0


def test_query_for_documents(lancedb_backend: LanceDBRAGBackend, sample_documents: list[Document]):
    """Test querying for documents and receiving ranked results."""
    lancedb_backend.add(sample_documents)

    query = RAGQueryRequest(text="brown fox", top_k=1)
    response = lancedb_backend.query(query)

    assert len(response.hits) == 1
    hit = response.hits[0]
    assert hit.document_id == "doc1"
    assert "quick brown fox" in hit.text
    assert hit.score > 0  # Should have some similarity


def test_delete_documents(lancedb_backend: LanceDBRAGBackend, sample_documents: list[Document]):
    """Test deleting documents by their IDs."""
    lancedb_backend.add(sample_documents)
    initial_count = lancedb_backend.count()
    assert initial_count > 0

    # Delete one document
    deleted_count = lancedb_backend.delete(["doc1"])
    assert deleted_count == 1

    # Query for the deleted document
    query = RAGQueryRequest(text="brown fox", top_k=1)
    response = lancedb_backend.query(query)

    # It might still return hits from the other document, but the doc_id should not be doc1
    if response.hits:
        assert all(hit.document_id != "doc1" for hit in response.hits)

def test_get_all_post_vectors(lancedb_backend: LanceDBRAGBackend, sample_documents: list[Document]):
    """Test retrieving all post vectors and their centroids."""
    lancedb_backend.add(sample_documents)

    doc_ids, vectors = lancedb_backend.get_all_post_vectors()

    assert len(doc_ids) == len(sample_documents)
    assert vectors.shape == (len(sample_documents), EMBEDDING_DIM)
    assert "doc1" in doc_ids
    assert "doc2" in doc_ids
