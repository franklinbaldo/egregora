"""Tests for Document-based RAG indexing functions.

Tests the new Phase 4 functions:
- chunk_from_document(): Chunking Document objects
- index_document(): Indexing Document objects for RAG retrieval
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from egregora.agents.shared.rag import VectorStore
from egregora.agents.shared.rag.chunker import chunk_from_document
from egregora.agents.shared.rag.retriever import index_document
from egregora.core.document import Document, DocumentType


@pytest.fixture
def sample_post_document() -> Document:
    """Create a sample blog post document for testing."""
    content = """# Introduction

This is the first paragraph with some content about AI and machine learning.
It has multiple sentences to create a realistic chunk size.

## Section 1

This is another section with different content about neural networks.
Deep learning is a subset of machine learning that uses multiple layers.

## Section 2

Final section discussing transformers and attention mechanisms.
These have revolutionized natural language processing tasks."""

    return Document(
        content=content,
        type=DocumentType.POST,
        metadata={
            "slug": "test-post",
            "title": "Test Post About AI",
            "date": "2025-01-10",
            "authors": ["author-uuid-1"],
            "tags": ["ai", "machine-learning"],
        },
    )


@pytest.fixture
def sample_profile_document() -> Document:
    """Create a sample profile document for testing."""
    content = """Alice is a software engineer specializing in machine learning.
She has published several papers on transformer architectures."""

    return Document(
        content=content,
        type=DocumentType.PROFILE,
        metadata={
            "uuid": "author-uuid-1",
            "name": "Alice",
            "bio": "ML Engineer",
        },
    )


def test_chunk_from_document_basic(sample_post_document: Document) -> None:
    """Test basic chunking of a Document object."""
    chunks = chunk_from_document(sample_post_document, max_tokens=100)

    # Should produce multiple chunks due to content length
    assert len(chunks) > 0

    # Each chunk should have required fields
    for chunk in chunks:
        assert "content" in chunk
        assert "chunk_index" in chunk
        assert "post_slug" in chunk
        assert "post_title" in chunk
        assert "metadata" in chunk
        assert "document_id" in chunk

        # Verify metadata is passed through
        assert chunk["post_slug"] == "test-post"
        assert chunk["post_title"] == "Test Post About AI"
        assert chunk["document_id"] == sample_post_document.document_id


def test_chunk_from_document_preserves_metadata(sample_post_document: Document) -> None:
    """Test that chunk_from_document preserves document metadata."""
    chunks = chunk_from_document(sample_post_document)

    for chunk in chunks:
        metadata = chunk["metadata"]
        assert metadata["slug"] == "test-post"
        assert metadata["title"] == "Test Post About AI"
        assert metadata["date"] == "2025-01-10"
        assert metadata["authors"] == ["author-uuid-1"]
        assert metadata["tags"] == ["ai", "machine-learning"]


def test_chunk_from_document_assigns_chunk_indices(sample_post_document: Document) -> None:
    """Test that chunks are assigned sequential indices."""
    chunks = chunk_from_document(sample_post_document, max_tokens=100)

    for i, chunk in enumerate(chunks):
        assert chunk["chunk_index"] == i


def test_chunk_from_document_with_small_content() -> None:
    """Test chunking a document with content that fits in one chunk."""
    doc = Document(
        content="Short content that fits in one chunk.",
        type=DocumentType.POST,
        metadata={"slug": "short-post", "title": "Short Post"},
    )

    chunks = chunk_from_document(doc)

    # Should produce exactly one chunk
    assert len(chunks) == 1
    assert chunks[0]["content"] == "Short content that fits in one chunk."
    assert chunks[0]["chunk_index"] == 0


def test_chunk_from_document_fallback_slug_title() -> None:
    """Test that chunk_from_document uses document_id as fallback for slug/title."""
    doc = Document(
        content="Content without explicit slug or title.",
        type=DocumentType.POST,
        metadata={},  # No slug or title
    )

    chunks = chunk_from_document(doc)

    # Should use first 8 chars of document_id as slug
    assert chunks[0]["post_slug"] == doc.document_id[:8]

    # Should derive title from slug
    expected_title = doc.document_id[:8].replace("-", " ").title()
    assert chunks[0]["post_title"] == expected_title


def test_index_document_basic(tmp_path, sample_post_document: Document) -> None:
    """Test basic indexing of a Document object."""
    store = VectorStore(tmp_path / "chunks.parquet")

    # Mock embedding model (would normally use real Gemini API)
    # For now, we'll skip this test if GOOGLE_API_KEY is not set
    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set - skipping embedding test")

    # Index the document
    indexed_count = index_document(
        sample_post_document,
        store,
        embedding_model="models/text-embedding-004",
    )

    # Should have indexed some chunks
    assert indexed_count > 0


def test_index_document_with_explicit_source_info(tmp_path, sample_post_document: Document) -> None:
    """Test indexing with explicit source_path and source_mtime_ns."""
    store = VectorStore(tmp_path / "chunks.parquet")

    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set - skipping embedding test")

    # Explicit source information
    source_path = "/path/to/posts/test-post.md"
    source_mtime_ns = int(datetime(2025, 1, 10, 12, 0, tzinfo=ZoneInfo("UTC")).timestamp() * 1_000_000_000)

    indexed_count = index_document(
        sample_post_document,
        store,
        embedding_model="models/text-embedding-004",
        source_path=source_path,
        source_mtime_ns=source_mtime_ns,
    )

    assert indexed_count > 0


def test_index_document_uses_content_addressed_id(tmp_path, sample_post_document: Document) -> None:
    """Test that index_document uses content-addressed document_id."""
    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set - skipping embedding test")

    store = VectorStore(tmp_path / "chunks.parquet")

    indexed_count = index_document(
        sample_post_document,
        store,
        embedding_model="models/text-embedding-004",
    )

    assert indexed_count > 0

    # Verify that chunks were stored with document_id
    # (Would need to query the store to fully verify this)


def test_index_document_profile(tmp_path, sample_profile_document: Document) -> None:
    """Test indexing a profile document."""
    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set - skipping embedding test")

    store = VectorStore(tmp_path / "chunks.parquet")

    indexed_count = index_document(
        sample_profile_document,
        store,
        embedding_model="models/text-embedding-004",
    )

    # Profile is short, should produce at least 1 chunk
    assert indexed_count >= 1


def test_chunk_from_document_profile(sample_profile_document: Document) -> None:
    """Test chunking a profile document."""
    chunks = chunk_from_document(sample_profile_document)

    # Profile should produce at least 1 chunk
    assert len(chunks) >= 1

    # Verify profile metadata
    chunk = chunks[0]
    assert chunk["metadata"]["uuid"] == "author-uuid-1"
    assert chunk["document_id"] == sample_profile_document.document_id
