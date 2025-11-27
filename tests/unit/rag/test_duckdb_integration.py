"""Tests for DuckDB integration with LanceDB RAG backend."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from egregora.rag import RAGQueryRequest
from egregora.rag.duckdb_integration import search_to_table, search_with_filters
from egregora.rag.models import RAGHit, RAGQueryResponse


@pytest.fixture
def mock_rag_response():
    """Create mock RAG response."""
    return RAGQueryResponse(
        hits=[
            RAGHit(
                document_id="doc-1",
                chunk_id="chunk-1",
                text="This is a test document about machine learning",
                score=0.92,
                metadata={"document_type": "POST", "slug": "ml-post"},
            ),
            RAGHit(
                document_id="doc-2",
                chunk_id="chunk-2",
                text="Another document discussing AI topics",
                score=0.85,
                metadata={"document_type": "POST", "slug": "ai-post"},
            ),
            RAGHit(
                document_id="doc-3",
                chunk_id="chunk-3",
                text="A note about neural networks",
                score=0.78,
                metadata={"document_type": "NOTE", "slug": "nn-note"},
            ),
        ]
    )


def test_search_to_table_basic(mock_rag_response):
    """Test converting RAG results to Ibis table."""
    with patch("egregora.rag.duckdb_integration.search") as mock_search:
        mock_search.return_value = mock_rag_response

        request = RAGQueryRequest(text="test query", top_k=5)
        table = search_to_table(request)

        # Verify table structure
        assert table is not None
        result = table.execute()

        # Verify all rows are present
        assert len(result) == 3

        # Verify columns
        assert "chunk_id" in result.columns
        assert "text" in result.columns
        assert "score" in result.columns
        assert "document_id" in result.columns
        assert "document_type" in result.columns

        # Verify data
        assert result.iloc[0]["chunk_id"] == "chunk-1"
        assert result.iloc[0]["score"] == 0.92
        assert "machine learning" in result.iloc[0]["text"]


def test_search_to_table_empty_results():
    """Test search_to_table with no results."""
    empty_response = RAGQueryResponse(hits=[])

    with patch("egregora.rag.duckdb_integration.search") as mock_search:
        mock_search.return_value = empty_response

        request = RAGQueryRequest(text="no results", top_k=5)
        table = search_to_table(request)

        result = table.execute()
        assert len(result) == 0
        # Verify empty table has expected columns
        assert "chunk_id" in result.columns


def test_search_to_table_with_sql_filtering(mock_rag_response):
    """Test filtering RAG results using SQL/Ibis."""
    with patch("egregora.rag.duckdb_integration.search") as mock_search:
        mock_search.return_value = mock_rag_response

        request = RAGQueryRequest(text="test", top_k=10)
        table = search_to_table(request)

        # Apply SQL-style filtering
        high_scores = table.filter(table.score > 0.8)
        result = high_scores.execute()

        # Should only have 2 results with score > 0.8
        assert len(result) == 2
        assert all(row["score"] > 0.8 for _, row in result.iterrows())


def test_search_with_filters_min_score(mock_rag_response):
    """Test search_with_filters with minimum score threshold."""
    with patch("egregora.rag.duckdb_integration.search") as mock_search:
        mock_search.return_value = mock_rag_response

        result_table = search_with_filters("test query", min_score=0.8, top_k=10)
        result = result_table.execute()

        # Should filter out score < 0.8
        assert len(result) == 2
        assert all(row["score"] >= 0.8 for _, row in result.iterrows())


def test_search_with_filters_document_type(mock_rag_response):
    """Test filtering by document type."""
    with patch("egregora.rag.duckdb_integration.search") as mock_search:
        mock_search.return_value = mock_rag_response

        result_table = search_with_filters("test query", min_score=0.0, document_types=["POST"], top_k=10)
        result = result_table.execute()

        # Should only have POST documents
        assert len(result) == 2
        assert all(row["document_type"] == "POST" for _, row in result.iterrows())


def test_search_with_filters_combined(mock_rag_response):
    """Test combining multiple filters."""
    with patch("egregora.rag.duckdb_integration.search") as mock_search:
        mock_search.return_value = mock_rag_response

        result_table = search_with_filters(
            "test query",
            min_score=0.85,
            document_types=["POST"],
            top_k=10,
        )
        result = result_table.execute()

        # Should have 2 POST docs with score >= 0.85
        assert len(result) == 2
        assert all(row["document_type"] == "POST" for _, row in result.iterrows())
        assert all(row["score"] >= 0.85 for _, row in result.iterrows())


def test_search_to_table_preserves_metadata(mock_rag_response):
    """Test that metadata fields are preserved as columns."""
    with patch("egregora.rag.duckdb_integration.search") as mock_search:
        mock_search.return_value = mock_rag_response

        request = RAGQueryRequest(text="test", top_k=5)
        table = search_to_table(request)
        result = table.execute()

        # Verify metadata fields are columns
        assert "document_id" in result.columns
        assert "document_type" in result.columns
        assert "slug" in result.columns

        # Verify metadata values
        assert result.iloc[0]["slug"] == "ml-post"
        assert result.iloc[1]["document_id"] == "doc-2"


def test_search_to_table_ordering(mock_rag_response):
    """Test that results are ordered by score."""
    with patch("egregora.rag.duckdb_integration.search") as mock_search:
        mock_search.return_value = mock_rag_response

        request = RAGQueryRequest(text="test", top_k=5)
        table = search_to_table(request)

        # Sort by score descending
        sorted_table = table.order_by(table.score.desc())
        result = sorted_table.execute()

        # Verify descending order
        scores = result["score"].tolist()
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 0.92  # Highest score first
