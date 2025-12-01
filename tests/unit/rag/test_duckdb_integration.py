"""Unit tests for DuckDB RAG integration (Synchronous)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.rag import (
    RAGBackend,
    RAGHit,
    RAGQueryRequest,
    RAGQueryResponse,
)
from egregora.rag.duckdb_integration import (
    create_rag_analytics_view,
    join_with_messages,
    search_to_table,
    search_with_filters,
)


@pytest.fixture
def mock_rag_response():
    """Create a mock RAG response."""
    return RAGQueryResponse(
        hits=[
            RAGHit(
                document_id="doc1",
                chunk_id="chunk1",
                text="Test document 1 about Python",
                score=0.9,
                metadata={"document_type": "POST", "slug": "test-1"},
            ),
            RAGHit(
                document_id="doc2",
                chunk_id="chunk2",
                text="Test document 2 about AI",
                score=0.8,
                metadata={"document_type": "POST", "slug": "test-2"},
            ),
            RAGHit(
                document_id="doc3",
                chunk_id="chunk3",
                text="Low score document",
                score=0.5,
                metadata={"document_type": "NOTE", "slug": "note-1"},
            ),
        ]
    )


def test_search_to_table_basic(mock_rag_response):
    """Test converting search results to Ibis table."""
    with patch("egregora.rag.duckdb_integration.search", return_value=mock_rag_response):
        request = RAGQueryRequest(text="test", top_k=3)
        table = search_to_table(request)

        # Execute to check results
        df = table.execute()
        assert len(df) == 3
        assert "score" in df.columns
        assert "text" in df.columns
        assert "document_type" in df.columns
        assert df.iloc[0]["document_id"] == "doc1"


def test_search_to_table_empty_results():
    """Test handling of empty search results."""
    empty_response = RAGQueryResponse(hits=[])
    with patch("egregora.rag.duckdb_integration.search", return_value=empty_response):
        request = RAGQueryRequest(text="empty", top_k=3)
        table = search_to_table(request)

        df = table.execute()
        assert len(df) == 0
        # Check expected columns exist even if empty
        assert "score" in df.columns
        assert "text" in df.columns


def test_search_with_filters(mock_rag_response):
    """Test search with SQL filtering."""
    with patch("egregora.rag.duckdb_integration.search", return_value=mock_rag_response):
        # Filter by min_score
        table = search_with_filters("test", min_score=0.85, top_k=10)
        df = table.execute()
        assert len(df) == 1
        assert df.iloc[0]["document_id"] == "doc1"

        # Filter by document_type
        table = search_with_filters("test", document_types=["NOTE"], min_score=0.0, top_k=10)
        df = table.execute()
        assert len(df) == 1
        assert df.iloc[0]["document_id"] == "doc3"


def test_search_to_table_preserves_metadata(mock_rag_response):
    """Test that metadata fields are preserved as columns."""
    with patch("egregora.rag.duckdb_integration.search", return_value=mock_rag_response):
        request = RAGQueryRequest(text="test", top_k=3)
        table = search_to_table(request)

        df = table.execute()
        assert "slug" in df.columns
        assert df.iloc[0]["slug"] == "test-1"
