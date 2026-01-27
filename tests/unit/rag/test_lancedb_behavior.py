"""Behavioral tests for LanceDB RAG backend."""

import pytest
<<<<<<< HEAD
=======
import numpy as np
from unittest.mock import MagicMock
from pathlib import Path
>>>>>>> origin/pr/2652

from egregora.data_primitives.document import Document, DocumentType
from egregora.rag.lancedb_backend import LanceDBRAGBackend
from egregora.rag.models import RAGQueryRequest

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
# Mock embedding function
def mock_embed_fn(texts, task_type):
    # Return random vectors of dim 768
    return [[0.1] * 768 for _ in texts]

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "lancedb"

<<<<<<< HEAD

@pytest.fixture
def backend(db_path):
    return LanceDBRAGBackend(db_dir=db_path, table_name="test_vectors", embed_fn=mock_embed_fn)

=======
@pytest.fixture
def backend(db_path):
    return LanceDBRAGBackend(
        db_dir=db_path,
        table_name="test_vectors",
        embed_fn=mock_embed_fn
    )
>>>>>>> origin/pr/2652

def test_add_and_query_documents(backend):
    """Verify adding documents and querying them."""
    # Given
    docs = [
        Document(content="Hello world", type=DocumentType.POST, metadata={"id": "doc1"}),
        Document(content="Another doc", type=DocumentType.POST, metadata={"id": "doc2"}),
    ]

    # When
    count = backend.add(docs)

    # Then
    assert count == 2
<<<<<<< HEAD
    assert backend.count() > 0  # Chunks count
=======
    assert backend.count() > 0 # Chunks count
>>>>>>> origin/pr/2652

    # Query
    response = backend.query(RAGQueryRequest(text="Hello", top_k=1))
    assert len(response.hits) == 1
    # Hits should return valid document IDs
    assert response.hits[0].document_id

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
def test_delete_documents(backend):
    """Verify deleting documents."""
    # Given
    doc = Document(content="To be deleted", type=DocumentType.POST)
    backend.add([doc])
    doc_id = doc.document_id

    # When
    backend.delete([doc_id])

    # Then
    # Query should return nothing or not this doc
    response = backend.query(RAGQueryRequest(text="deleted", top_k=5))
    ids = [h.document_id for h in response.hits]
    assert doc_id not in ids

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2652
def test_add_updates_existing(backend):
    """Verify adding same document updates it (idempotency)."""
    # Given
    doc = Document(content="Original content", type=DocumentType.POST)
    backend.add([doc])
    initial_count = backend.count()

    # When
    # Re-adding exact same document
    backend.add([doc])

    # Then
<<<<<<< HEAD
    assert backend.count() == initial_count  # Should not duplicate chunks

=======
    assert backend.count() == initial_count # Should not duplicate chunks
>>>>>>> origin/pr/2652

def test_persistence(db_path):
    """Verify data persists across instances."""
    # Given
    backend1 = LanceDBRAGBackend(db_path, "persist", mock_embed_fn)
    doc = Document(content="Persistent", type=DocumentType.POST)
    backend1.add([doc])

    # When
    backend2 = LanceDBRAGBackend(db_path, "persist", mock_embed_fn)

    # Then
    assert backend2.count() > 0
    response = backend2.query(RAGQueryRequest(text="Persistent", top_k=1))
    assert len(response.hits) > 0
