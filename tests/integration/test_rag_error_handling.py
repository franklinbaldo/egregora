"""Tests for RAG error handling and observability."""

from unittest.mock import Mock, patch

import ibis
import pytest
from returns.result import Failure, Success

from egregora.agents.writer.context import (
    RagContext,
    RagErrorReason,
    _query_rag_for_context,
)
from egregora.utils import GeminiBatchClient


@pytest.fixture
def mock_table():
    """Create a mock Ibis table."""
    return Mock(spec=ibis.expr.types.Table)


@pytest.fixture
def mock_batch_client():
    """Create a mock GeminiBatchClient."""
    return Mock(spec=GeminiBatchClient)


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

    @patch("egregora.agents.writer.context.VectorStore")
    @patch("egregora.agents.writer.context.query_similar_posts")
    def test_rag_error_returns_failure_result(
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir
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

    @patch("egregora.agents.writer.context.VectorStore")
    @patch("egregora.agents.writer.context.query_similar_posts")
    def test_no_hits_returns_failure_result(
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that no hits return Failure result."""
        # Mock empty result
        mock_result = Mock()
        mock_result.count.return_value.execute.return_value = 0
        mock_query.return_value = mock_result

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
        )

        assert isinstance(result, Failure)
        failure_reason = result.failure()
        assert failure_reason == RagErrorReason.NO_HITS

    @patch("egregora.agents.writer.context.VectorStore")
    @patch("egregora.agents.writer.context.query_similar_posts")
    def test_successful_query_returns_success_result(
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that successful queries return Success result."""
        # Mock successful result
        mock_result = Mock()
        mock_result.count.return_value.execute.return_value = 2

        mock_records = [
            {
                "post_title": "Test Post 1",
                "post_date": "2025-01-01",
                "content": "Test content 1",
                "tags": ["test", "python"],
                "similarity": 0.95,
            },
            {
                "post_title": "Test Post 2",
                "post_date": "2025-01-02",
                "content": "Test content 2",
                "tags": [],
                "similarity": 0.87,
            },
        ]
        mock_result.execute.return_value.to_dict.return_value = mock_records
        mock_query.return_value = mock_result

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
        assert len(context.records) == 2  # noqa: PLR2004

    @patch("egregora.agents.writer.context.VectorStore")
    @patch("egregora.agents.writer.context.query_similar_posts")
    def test_return_records_backward_compatibility(
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that return_records=True maintains backward compatibility."""
        # Mock successful result
        mock_result = Mock()
        mock_result.count.return_value.execute.return_value = 1

        mock_records = [
            {
                "post_title": "Test Post",
                "post_date": "2025-01-01",
                "content": "Test content",
                "tags": ["test"],
                "similarity": 0.95,
            }
        ]
        mock_result.execute.return_value.to_dict.return_value = mock_records
        mock_query.return_value = mock_result

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
            return_records=True,
        )

        # Should return tuple for backward compatibility
        assert isinstance(result, tuple)
        assert len(result) == 2  # noqa: PLR2004
        text, records = result
        assert isinstance(text, str)
        assert isinstance(records, list)
        assert "Test Post" in text

    @patch("egregora.agents.writer.context.VectorStore")
    @patch("egregora.agents.writer.context.query_similar_posts")
    def test_return_records_error_case(
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir
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

    @patch("egregora.agents.writer.context.VectorStore")
    @patch("egregora.agents.writer.context.query_similar_posts")
    def test_rag_error_logging(  # noqa: PLR0913
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir, caplog
    ):
        """Test that RAG errors are logged with full traceback."""
        import logging

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
