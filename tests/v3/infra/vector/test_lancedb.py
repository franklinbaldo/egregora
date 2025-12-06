"""TDD tests for LanceDB Vector Store - written BEFORE implementation.

Tests for V3 LanceDBVectorStore:
- index_documents(docs: list[Document]) -> None
- search(query: str, top_k: int = 5) -> list[Document]

Following TDD Red-Green-Refactor cycle.
"""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from faker import Faker

from egregora_v3.core.types import Author, Document, DocumentStatus, DocumentType
from egregora_v3.infra.vector.lancedb import LanceDBVectorStore

fake = Faker()


# ========== Fixtures ==========


@pytest.fixture
def mock_embed_fn():
    """Simple mock embedding function for testing.

    Returns fixed-size random vectors for any text.
    """

    def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        """Generate random embeddings for texts."""
        # Return consistent random vectors based on text hash
        return [
            [float(hash(text + str(i)) % 1000) / 1000.0 for i in range(768)]
            for text in texts
        ]

    return embed


@pytest.fixture
def vector_store(tmp_path: Path, mock_embed_fn) -> LanceDBVectorStore:
    """Create LanceDB vector store for testing."""
    db_dir = tmp_path / "lancedb"
    return LanceDBVectorStore(
        db_dir=db_dir,
        table_name="test_vectors",
        embed_fn=mock_embed_fn,
    )


@pytest.fixture
def sample_documents() -> list[Document]:
    """Create sample documents for testing."""
    doc1 = Document.create(
        content="# Python Tutorial\n\nPython is a high-level programming language.",
        doc_type=DocumentType.POST,
        title="Python Tutorial",
        status=DocumentStatus.PUBLISHED,
    )
    doc1.authors = [Author(name="Alice")]

    doc2 = Document.create(
        content="# JavaScript Guide\n\nJavaScript is the language of the web.",
        doc_type=DocumentType.POST,
        title="JavaScript Guide",
        status=DocumentStatus.PUBLISHED,
    )
    doc2.authors = [Author(name="Bob")]

    doc3 = Document.create(
        content="# Rust Programming\n\nRust is a systems programming language.",
        doc_type=DocumentType.POST,
        title="Rust Programming",
        status=DocumentStatus.PUBLISHED,
    )

    return [doc1, doc2, doc3]


# ========== Initialization Tests ==========


def test_vector_store_creates_database_directory(tmp_path: Path, mock_embed_fn) -> None:
    """Test that vector store creates database directory."""
    db_dir = tmp_path / "new_lancedb"
    store = LanceDBVectorStore(
        db_dir=db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    assert db_dir.exists()


def test_vector_store_creates_table(vector_store: LanceDBVectorStore) -> None:
    """Test that vector store creates a table."""
    # Index a single document to ensure table exists
    doc = Document.create(
        content="Test content",
        doc_type=DocumentType.POST,
        title="Test",
    )
    vector_store.index_documents([doc])

    # Table should exist after indexing
    assert "test_vectors" in vector_store._db.table_names()


# ========== Indexing Tests ==========


def test_index_single_document(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test indexing a single document."""
    vector_store.index_documents([sample_documents[0]])

    # Search should find the document
    results = vector_store.search("Python programming", top_k=1)
    assert len(results) > 0


def test_index_multiple_documents(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test indexing multiple documents."""
    vector_store.index_documents(sample_documents)

    # All documents should be searchable
    results = vector_store.search("programming language", top_k=5)
    assert len(results) == 3


def test_index_empty_list(vector_store: LanceDBVectorStore) -> None:
    """Test indexing empty list of documents."""
    # Should not raise
    vector_store.index_documents([])


def test_index_documents_with_unicode_content(
    vector_store: LanceDBVectorStore,
) -> None:
    """Test indexing documents with Unicode content."""
    doc = Document.create(
        content="Unicode content: 你好世界 🎉 Olá",
        doc_type=DocumentType.POST,
        title="Unicode Test",
        status=DocumentStatus.PUBLISHED,
    )

    vector_store.index_documents([doc])

    results = vector_store.search("Unicode", top_k=1)
    assert len(results) > 0


def test_index_updates_existing_document(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test that re-indexing a document updates it."""
    # Index original
    doc = sample_documents[0]
    vector_store.index_documents([doc])

    # Update content
    doc.content = "# Updated Python Tutorial\n\nThis is updated content."
    vector_store.index_documents([doc])

    # Search should find updated version
    results = vector_store.search("Python", top_k=1)
    assert len(results) > 0
    assert "updated content" in results[0].content.lower()


# ========== Search Tests ==========


def test_search_returns_documents(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test that search returns Document objects."""
    vector_store.index_documents(sample_documents)

    results = vector_store.search("Python", top_k=1)

    assert len(results) > 0
    assert all(isinstance(doc, Document) for doc in results)


def test_search_respects_top_k(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test that search respects top_k parameter."""
    vector_store.index_documents(sample_documents)

    # Request only 2 results
    results = vector_store.search("programming", top_k=2)
    assert len(results) <= 2


def test_search_empty_query(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test search with empty query string."""
    vector_store.index_documents(sample_documents)

    # Empty query should still return results (based on random embeddings)
    results = vector_store.search("", top_k=1)
    # Results may or may not be empty depending on implementation
    assert isinstance(results, list)


def test_search_on_empty_store(vector_store: LanceDBVectorStore) -> None:
    """Test search on empty vector store."""
    # Search should return empty list
    results = vector_store.search("anything", top_k=5)
    assert results == []


def test_search_preserves_document_metadata(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test that search preserves document metadata."""
    vector_store.index_documents(sample_documents)

    results = vector_store.search("Python", top_k=1)

    assert len(results) > 0
    result = results[0]

    # Check all fields are preserved
    assert result.id
    assert result.title
    assert result.content
    assert result.doc_type == DocumentType.POST
    assert result.status == DocumentStatus.PUBLISHED


def test_search_unicode_query(
    vector_store: LanceDBVectorStore,
) -> None:
    """Test search with Unicode query."""
    doc = Document.create(
        content="Chinese content: 你好世界",
        doc_type=DocumentType.POST,
        title="Chinese Post",
    )
    vector_store.index_documents([doc])

    # Unicode query should work
    results = vector_store.search("你好", top_k=1)
    assert isinstance(results, list)


# ========== Document Reconstruction Tests ==========


def test_reconstructed_document_has_all_fields(
    vector_store: LanceDBVectorStore,
) -> None:
    """Test that reconstructed documents have all required fields."""
    doc = Document.create(
        content="# Test Post\n\nContent here.",
        doc_type=DocumentType.POST,
        title="Test Post",
        status=DocumentStatus.PUBLISHED,
    )
    doc.summary = "Test summary"
    doc.published = datetime(2025, 12, 5, tzinfo=UTC)
    doc.authors = [Author(name="Alice", email="alice@example.com")]

    vector_store.index_documents([doc])

    results = vector_store.search("Test", top_k=1)
    assert len(results) > 0

    result = results[0]
    assert result.id == doc.id
    assert result.title == doc.title
    assert result.content == doc.content
    assert result.summary == doc.summary
    assert result.doc_type == doc.doc_type
    assert result.status == doc.status
    # Timestamps and authors should be preserved


def test_document_roundtrip_preserves_id(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test that document ID survives indexing and retrieval."""
    original_doc = sample_documents[0]
    original_id = original_doc.id

    vector_store.index_documents([original_doc])

    results = vector_store.search(original_doc.title, top_k=1)
    assert len(results) > 0
    assert results[0].id == original_id


# ========== Edge Cases ==========


def test_index_document_with_very_long_content(
    vector_store: LanceDBVectorStore,
) -> None:
    """Test indexing document with very long content."""
    # 100KB of content
    long_content = "x" * (100 * 1024)

    doc = Document.create(
        content=long_content,
        doc_type=DocumentType.POST,
        title="Long Document",
    )

    vector_store.index_documents([doc])

    results = vector_store.search("Long Document", top_k=1)
    assert len(results) > 0


def test_index_document_with_minimal_fields(
    vector_store: LanceDBVectorStore,
) -> None:
    """Test indexing document with only required fields."""
    # Minimal document (no summary, authors, etc.)
    doc = Document.create(
        content="Minimal content",
        doc_type=DocumentType.NOTE,
        title="Minimal",
    )

    vector_store.index_documents([doc])

    results = vector_store.search("Minimal", top_k=1)
    assert len(results) > 0


def test_multiple_searches_are_independent(
    vector_store: LanceDBVectorStore, sample_documents: list[Document]
) -> None:
    """Test that multiple searches don't interfere with each other."""
    vector_store.index_documents(sample_documents)

    # Run multiple searches
    results1 = vector_store.search("Python", top_k=1)
    results2 = vector_store.search("JavaScript", top_k=1)
    results3 = vector_store.search("Rust", top_k=1)

    # All should return results
    assert len(results1) > 0
    assert len(results2) > 0
    assert len(results3) > 0


# ========== Integration Tests ==========


def test_index_and_search_workflow(
    vector_store: LanceDBVectorStore,
) -> None:
    """Test complete index and search workflow."""
    # Create documents
    docs = [
        Document.create(
            content=fake.text(max_nb_chars=200),
            doc_type=DocumentType.POST,
            title=fake.sentence(),
            status=DocumentStatus.PUBLISHED,
        )
        for _ in range(5)
    ]

    # Index documents
    vector_store.index_documents(docs)

    # Search should work
    results = vector_store.search("content", top_k=3)

    # Should return up to 3 results
    assert len(results) <= 3
    assert all(isinstance(doc, Document) for doc in results)
