"""Unit tests for LanceDB RAG backend."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.rag.lancedb_backend import LanceDBRAGBackend
from egregora.rag.models import RAGQueryRequest


@pytest.fixture
def temp_db_dir() -> Path:
    """Create a temporary directory for LanceDB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_embed_fn():
    """Create a mock embedding function that returns fixed-size vectors."""

    def embed(texts: list[str], task_type: str) -> list[list[float]]:
        # Return random 768-dimensional embeddings using a Generator
        rng = np.random.default_rng(seed=42)
        return [rng.random(768).tolist() for _ in texts]

    return embed


def test_lancedb_backend_initialization(temp_db_dir: Path, mock_embed_fn):
    """Test that LanceDBRAGBackend initializes correctly."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test_embeddings",
        embed_fn=mock_embed_fn,
    )

    assert backend is not None
    assert backend._db_dir == temp_db_dir
    assert backend._table_name == "test_embeddings"


def test_lancedb_backend_index_documents(temp_db_dir: Path, mock_embed_fn):
    """Test indexing documents into LanceDB."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test_embeddings",
        embed_fn=mock_embed_fn,
    )

    # Create test documents
    docs = [
        Document(
            content="# Test Post 1\n\nThis is the first test post.",
            type=DocumentType.POST,
            metadata={"title": "Test Post 1", "slug": "test-post-1"},
        ),
        Document(
            content="# Test Post 2\n\nThis is the second test post.",
            type=DocumentType.POST,
            metadata={"title": "Test Post 2", "slug": "test-post-2"},
        ),
    ]

    # Index documents (should not raise)
    backend.add(docs)


def test_lancedb_backend_query(temp_db_dir: Path, mock_embed_fn):
    """Test querying the LanceDB backend."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test_embeddings",
        embed_fn=mock_embed_fn,
    )

    # Create and index test documents
    docs = [
        Document(
            content="# Test Post 1\n\nThis is the first test post about cats.",
            type=DocumentType.POST,
            metadata={"title": "Test Post 1", "slug": "test-post-1"},
        ),
        Document(
            content="# Test Post 2\n\nThis is the second test post about dogs.",
            type=DocumentType.POST,
            metadata={"title": "Test Post 2", "slug": "test-post-2"},
        ),
    ]

    backend.add(docs)

    # Query for documents
    request = RAGQueryRequest(text="cats and dogs", top_k=2)
    response = backend.query(request)

    # Should return results
    assert response is not None
    assert len(response.hits) <= 2
    # With random embeddings, scores can be any value (including negative)
    # Just check that we got valid hits with document IDs
    assert all(hit.document_id for hit in response.hits)
    assert all(hit.chunk_id for hit in response.hits)
    assert all(hit.text for hit in response.hits)


def test_lancedb_backend_empty_query(temp_db_dir: Path, mock_embed_fn):
    """Test querying an empty database."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test_embeddings",
        embed_fn=mock_embed_fn,
    )

    # Query without indexing anything
    request = RAGQueryRequest(text="test query", top_k=5)
    response = backend.query(request)

    # Should return empty results
    assert response is not None
    assert len(response.hits) == 0


def test_lancedb_backend_index_binary_content(temp_db_dir: Path, mock_embed_fn):
    """Test that binary content is skipped during indexing."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test_embeddings",
        embed_fn=mock_embed_fn,
    )

    # Create document with binary content
    docs = [
        Document(
            content=b"binary content",
            type=DocumentType.MEDIA,
            metadata={"filename": "test.jpg"},
        ),
    ]

    # Should not raise, but should skip the binary document
    backend.add(docs)
