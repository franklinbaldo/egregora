"""Tests for RAG error handling and observability."""

import logging
from unittest.mock import Mock, patch

import ibis
import pytest
from google import genai
from returns.result import Failure, Success

from egregora.agents.writer.context_builder import (
    RagContext,
    RagErrorReason,
    _query_rag_for_context,
)


@pytest.fixture
def mock_table():
    """Create a mock Ibis table."""
    return Mock(spec=ibis.expr.types.Table)


@pytest.fixture
def mock_batch_client():
    """Create a mock genai.Client."""
    return Mock(spec=genai.Client)


@pytest.fixture
def test_rag_dir(tmp_path):
    """Create a temporary RAG directory."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    return rag_dir


class TestRagContext:
    """Tests for RagContext dataclass."""

    def test_success_context(self):
        """Test creating a successful context."""
        context = RagContext(text="Test content", records=[{"post_title": "Test"}])
        assert context.text == "Test content"
        assert len(context.records) == 1

    def test_error_reasons(self):
        """Test error reason constants."""
        assert RagErrorReason.NO_HITS == "no_hits"
        assert RagErrorReason.SYSTEM_ERROR == "rag_error"


class TestRagErrorHandling:
    """Tests for RAG error handling."""

    @patch("egregora.agents.writer.context_builder.VectorStore")
    @patch("egregora.agents.writer.context_builder.consolidate_messages_to_markdown")
    def test_rag_error_returns_failure_result(
        self, mock_consolidate, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that RAG errors return Failure result."""
        # Simulate VectorStore raising an exception
        mock_store.side_effect = Exception("Index file not found")

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
        )

        assert isinstance(result, Failure)
        failure_reason = result.failure()
        assert failure_reason == RagErrorReason.SYSTEM_ERROR

    @patch("egregora.agents.writer.context_builder.VectorStore")
    @patch("egregora.agents.writer.context_builder.consolidate_messages_to_markdown")
    @patch("egregora.agents.writer.context_builder.chunk_markdown")
    @patch("egregora.agents.writer.context_builder.query_rag_per_chunk")
    def test_no_hits_returns_failure_result(
        self, mock_query_chunks, mock_chunk, mock_consolidate, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that no hits return Failure result."""
        # Mock consolidation and empty chunk query results
        mock_consolidate.return_value = "Test conversation"
        mock_chunk.return_value = ["chunk1"]
        mock_query_chunks.return_value = []  # Empty results

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
        )

        assert isinstance(result, Failure)
        failure_reason = result.failure()
        assert failure_reason == RagErrorReason.NO_HITS

    @patch("egregora.agents.writer.context_builder.VectorStore")
    @patch("egregora.agents.writer.context_builder.consolidate_messages_to_markdown")
    @patch("egregora.agents.writer.context_builder.chunk_markdown")
    @patch("egregora.agents.writer.context_builder.query_rag_per_chunk")
    def test_successful_query_returns_success_result(
        self, mock_query_chunks, mock_chunk, mock_consolidate, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that successful queries return Success result."""
        # Mock the full chunked pipeline
        mock_consolidate.return_value = "Test conversation"
        mock_chunk.return_value = ["chunk1"]

        mock_records = [
            {
                "document_id": "post-1",
                "post_title": "Test Post 1",
                "post_date": "2025-01-01",
                "content": "Test content 1",
                "tags": ["test", "python"],
                "similarity": 0.95,
            },
            {
                "document_id": "post-2",
                "post_title": "Test Post 2",
                "post_date": "2025-01-02",
                "content": "Test content 2",
                "tags": [],
                "similarity": 0.87,
            },
        ]
        mock_query_chunks.return_value = mock_records

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
        )

        assert isinstance(result, Success)
        context = result.unwrap()
        assert isinstance(context, RagContext)
        assert context.text != ""
        assert "Test Post 1" in context.text
        assert "Test Post 2" in context.text
        assert len(context.records) == 2

    @patch("egregora.agents.writer.context_builder.VectorStore")
    @patch("egregora.agents.writer.context_builder.consolidate_messages_to_markdown")
    @patch("egregora.agents.writer.context_builder.chunk_markdown")
    @patch("egregora.agents.writer.context_builder.query_rag_per_chunk")
    def test_return_records_backward_compatibility(
        self, mock_query_chunks, mock_chunk, mock_consolidate, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that return_records=True maintains backward compatibility."""
        # Mock the full chunked pipeline
        mock_consolidate.return_value = "Test conversation"
        mock_chunk.return_value = ["chunk1"]

        mock_records = [
            {
                "document_id": "post-1",
                "post_title": "Test Post",
                "post_date": "2025-01-01",
                "content": "Test content",
                "tags": ["test"],
                "similarity": 0.95,
            }
        ]
        mock_query_chunks.return_value = mock_records

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
            return_records=True,
        )

        # Should return tuple for backward compatibility
        assert isinstance(result, tuple)
        assert len(result) == 2
        text, records = result
        assert isinstance(text, str)
        assert isinstance(records, list)
        assert "Test Post" in text

    @patch("egregora.agents.writer.context_builder.VectorStore")
    @patch("egregora.agents.writer.context_builder.consolidate_messages_to_markdown")
    def test_return_records_error_case(
        self, mock_consolidate, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that return_records=True handles errors correctly."""
        # Simulate error
        mock_store.side_effect = Exception("Database error")

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
            return_records=True,
        )

        # Should return empty tuple for backward compatibility
        assert result == ("", [])

    @patch("egregora.agents.writer.context_builder.VectorStore")
    @patch("egregora.agents.writer.context_builder.consolidate_messages_to_markdown")
    def test_rag_error_logging(
        self, mock_consolidate, mock_store, mock_table, mock_batch_client, test_rag_dir, caplog
    ):
        """Test that RAG errors are logged with full traceback."""
        caplog.set_level(logging.ERROR)

        # Simulate error
        mock_store.side_effect = ValueError("Invalid index format")

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
        )

        # Result is a Failure with error reason
        assert isinstance(result, Failure)
        failure_reason = result.failure()
        assert failure_reason == RagErrorReason.SYSTEM_ERROR
        # Check that error was logged
        assert "RAG query failed" in caplog.text
        assert "Invalid index format" in caplog.text
