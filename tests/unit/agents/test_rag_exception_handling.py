"""Unit tests for RAG exception handling during post-write indexing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from egregora.data_primitives.document import Document, DocumentType


class TestRAGExceptionHandling:
    """Tests verifying graceful degradation on RAG failures at caller level."""

    def test_exception_during_indexing_is_caught(self):
        """Verify exceptions during RAG indexing don't crash post generation."""
        from egregora.agents.writer import _index_new_content_in_rag

        mock_resources = Mock()
        mock_resources.retrieval_config = Mock()
        mock_resources.retrieval_config.enabled = True
        mock_resources.output = Mock()

        # Mock the documents iterator to return a test document
        test_doc = Document(
            content="# Test Post\n\nTest content",
            type=DocumentType.POST,
            metadata={"slug": "test-post"},
        )
        mock_resources.output.documents = Mock(return_value=[test_doc])

        # Mock index_documents to raise an exception
        with patch("egregora.rag.index_documents") as mock_index:
            mock_index.side_effect = RuntimeError("Database connection failed")

            # Should not raise - error is caught and logged
            _index_new_content_in_rag(mock_resources, saved_posts=["test-post"], saved_profiles=[])

            # Verify index_documents was called
            mock_index.assert_called_once()

    def test_successful_indexing_logs_count(self, caplog):
        """Verify successful indexing logs the indexed document count."""
        from egregora.agents.writer import _index_new_content_in_rag

        mock_resources = Mock()
        mock_resources.retrieval_config = Mock()
        mock_resources.retrieval_config.enabled = True
        mock_resources.output = Mock()

        # Mock the documents iterator to return test documents
        test_docs = [
            Document(
                content=f"# Test Post {i}\n\nTest content",
                type=DocumentType.POST,
                metadata={"slug": f"test-post-{i}"},
            )
            for i in range(3)
        ]
        mock_resources.output.documents = Mock(return_value=test_docs)

        with patch("egregora.rag.index_documents") as mock_index:
            with caplog.at_level("INFO"):
                _index_new_content_in_rag(
                    mock_resources, saved_posts=["test-post-0", "test-post-1", "test-post-2"], saved_profiles=[]
                )

            # Verify indexing was called
            mock_index.assert_called_once()
            # Verify log message
            assert "Indexed 3 new posts in RAG" in caplog.text

    def test_no_indexing_when_rag_disabled(self):
        """Verify indexing is skipped when RAG is disabled."""
        from egregora.agents.writer import _index_new_content_in_rag

        mock_resources = Mock()
        mock_resources.retrieval_config = Mock()
        mock_resources.retrieval_config.enabled = False
        mock_resources.output = Mock()

        with patch("egregora.rag.index_documents") as mock_index:
            _index_new_content_in_rag(mock_resources, saved_posts=["test-post"], saved_profiles=[])

            # Should not attempt indexing when disabled
            mock_index.assert_not_called()

    def test_no_indexing_when_no_posts_saved(self):
        """Verify indexing is skipped when no posts were saved."""
        from egregora.agents.writer import _index_new_content_in_rag

        mock_resources = Mock()
        mock_resources.retrieval_config = Mock()
        mock_resources.retrieval_config.enabled = True
        mock_resources.output = Mock()

        with patch("egregora.rag.index_documents") as mock_index:
            # No posts or profiles saved (empty lists)
            _index_new_content_in_rag(mock_resources, saved_posts=[], saved_profiles=[])

            # Should not attempt indexing
            mock_index.assert_not_called()


class TestPipelineRAGExceptionHandling:
    """Tests for RAG exception handling in write_pipeline.py."""

    def test_prepare_pipeline_catches_exceptions(self):
        """Verify pipeline catches exceptions during RAG indexing."""
        import inspect

        from egregora.orchestration.write_pipeline import _prepare_pipeline_data

        source = inspect.getsource(_prepare_pipeline_data)
        # Should use broad exception handling (non-critical path)
        assert "except Exception:" in source
        # Should have RAG indexing code
        assert "from egregora.rag import index_documents" in source
        assert "index_documents(existing_docs)" in source

    def test_index_media_is_disabled(self):
        """Verify media indexing is currently disabled (will be re-implemented)."""
        import inspect

        from egregora.orchestration.write_pipeline import _index_media_into_rag

        source = inspect.getsource(_index_media_into_rag)
        # Media RAG indexing is currently disabled
        assert "# Media RAG indexing removed" in source or "will be reimplemented" in source.lower()
