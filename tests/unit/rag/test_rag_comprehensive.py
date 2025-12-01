"""Comprehensive tests for RAG functionality (Synchronous)."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from egregora.config import EMBEDDING_DIM
from egregora.data_primitives.document import Document, DocumentType
from egregora.rag import (
    RAGBackend,
    RAGHit,
    RAGQueryRequest,
    get_backend,
    index_documents,
    reset_backend,
    search,
)
from egregora.rag.lancedb_backend import LanceDBRAGBackend

logger = logging.getLogger(__name__)


@pytest.fixture
def temp_db_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for the vector database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        yield path


@pytest.fixture
def mock_embed_fn():
    """Create a deterministic mock embedding function."""

    def embed(texts: list[str], task_type: str) -> list[list[float]]:
        # Return deterministic embedding based on text length
        embeddings = []
        for text in texts:
            # Seed based on text content for determinism
            seed = sum(ord(c) for c in text)
            rng = np.random.default_rng(seed)
            emb = rng.random(EMBEDDING_DIM).tolist()
            embeddings.append(emb)
        return embeddings

    return embed


@pytest.fixture
def mock_embed_fn_similar():
    """Create a mock embedding function where 'cats' and 'dogs' are similar."""

    def embed(texts: list[str], task_type: str) -> list[list[float]]:
        embeddings = []
        for text in texts:
            # Simple heuristic: if "cat" or "dog" in text, use similar vector
            if "cat" in text.lower() or "dog" in text.lower():
                # Base vector for animals
                base = np.zeros(EMBEDDING_DIM)
                base[0] = 1.0  # Strong signal in dimension 0
                # Add noise
                seed = sum(ord(c) for c in text)
                rng = np.random.default_rng(seed)
                noise = rng.random(EMBEDDING_DIM) * 0.1
                embeddings.append((base + noise).tolist())
            else:
                # Random vector
                seed = sum(ord(c) for c in text)
                rng = np.random.default_rng(seed)
                embeddings.append(rng.random(EMBEDDING_DIM).tolist())
        return embeddings

    return embed


def test_backend_index_documents(temp_db_dir: Path, mock_embed_fn):
    """Test indexing documents."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test_index",
        embed_fn=mock_embed_fn,
    )

    docs = [
        Document(content="Test document 1", type=DocumentType.POST),
        Document(content="Test document 2", type=DocumentType.POST),
    ]

    backend.index_documents(docs)

    # Verify data is in LanceDB
    tbl = backend._db.open_table("test_index")
    assert len(tbl) == 2


def test_backend_query_basic(temp_db_dir: Path, mock_embed_fn_similar):
    """Test basic query functionality."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test_query",
        embed_fn=mock_embed_fn_similar,
    )

    docs = [
        Document(content="Cats are great pets.", type=DocumentType.POST, metadata={"id": "1"}),
        Document(content="Dogs are loyal friends.", type=DocumentType.POST, metadata={"id": "2"}),
        Document(content="Python programming is fun.", type=DocumentType.POST, metadata={"id": "3"}),
    ]

    backend.index_documents(docs)

    # Search for "kitten" (should match cat/dog more than python)
    # Note: Our mock embedding is very simple, so we search for "cat"
    request = RAGQueryRequest(text="cat", top_k=2)
    response = backend.query(request)

    assert len(response.hits) == 2
    # Should find the animal docs
    texts = [h.text for h in response.hits]
    assert "Cats are great pets." in texts
    assert "Dogs are loyal friends." in texts


def test_high_level_api_index_and_search(temp_db_dir: Path, mock_embed_fn):
    """Test the high-level API functions."""
    # Reset backend to clear previous state
    reset_backend()

    # Mock the backend creation to inject our temp dir and mock embedder
    with patch("egregora.rag._create_backend") as mock_create:
        backend = LanceDBRAGBackend(
            db_dir=temp_db_dir,
            table_name="rag_embeddings",
            embed_fn=mock_embed_fn,
        )
        mock_create.return_value = backend

        docs = [Document(content="High level API test", type=DocumentType.POST)]
        index_documents(docs)

        request = RAGQueryRequest(text="test", top_k=1)
        response = search(request)

        assert len(response.hits) == 1
        assert response.hits[0].text == "High level API test"
