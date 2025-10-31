"""Tests for RAG error handling and observability."""

from pathlib import Path
from unittest.mock import Mock, patch

import ibis
import pytest

from egregora.generation.writer.context import RagResult, _query_rag_for_context
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


class TestRagResult:
    """Tests for RagResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = RagResult(ok=True, text="Test content", reason="success")
        assert result.ok is True
        assert result.text == "Test content"
        assert result.reason == "success"

    def test_no_hits_result(self):
        """Test creating a no-hits result."""
        result = RagResult(ok=False, reason="no_hits")
        assert result.ok is False
        assert result.text == ""
        assert result.reason == "no_hits"

    def test_error_result(self):
        """Test creating an error result."""
        result = RagResult(ok=False, reason="rag_error")
        assert result.ok is False
        assert result.text == ""
        assert result.reason == "rag_error"


class TestRagErrorHandling:
    """Tests for RAG error handling."""

    @patch("egregora.generation.writer.context.VectorStore")
    @patch("egregora.generation.writer.context.query_similar_posts")
    def test_rag_error_returns_structured_result(
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that RAG errors return structured RagResult."""
        # Simulate VectorStore raising an exception
        mock_store.side_effect = Exception("Index file not found")

        result = _query_rag_for_context(
            mock_table,
            mock_batch_client,
            test_rag_dir,
            embedding_model="models/text-embedding-004",
        )

        assert isinstance(result, RagResult)
        assert result.ok is False
        assert result.reason == "rag_error"
        assert result.text == ""

    @patch("egregora.generation.writer.context.VectorStore")
    @patch("egregora.generation.writer.context.query_similar_posts")
    def test_no_hits_returns_structured_result(
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that no hits return structured RagResult."""
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

        assert isinstance(result, RagResult)
        assert result.ok is False
        assert result.reason == "no_hits"
        assert result.text == ""

    @patch("egregora.generation.writer.context.VectorStore")
    @patch("egregora.generation.writer.context.query_similar_posts")
    def test_successful_query_returns_structured_result(
        self, mock_query, mock_store, mock_table, mock_batch_client, test_rag_dir
    ):
        """Test that successful queries return structured RagResult."""
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

        assert isinstance(result, RagResult)
        assert result.ok is True
        assert result.reason == "success"
        assert result.text != ""
        assert "Test Post 1" in result.text
        assert "Test Post 2" in result.text

    @patch("egregora.generation.writer.context.VectorStore")
    @patch("egregora.generation.writer.context.query_similar_posts")
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
        assert len(result) == 2
        text, records = result
        assert isinstance(text, str)
        assert isinstance(records, list)
        assert "Test Post" in text

    @patch("egregora.generation.writer.context.VectorStore")
    @patch("egregora.generation.writer.context.query_similar_posts")
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

    @patch("egregora.generation.writer.context.VectorStore")
    @patch("egregora.generation.writer.context.query_similar_posts")
    def test_rag_error_logging(
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

        assert result.reason == "rag_error"
        # Check that error was logged
        assert "RAG query failed" in caplog.text
        assert "Invalid index format" in caplog.text
