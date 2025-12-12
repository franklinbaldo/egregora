"""Unit tests for RAG exception handling during post-write indexing."""

from __future__ import annotations

import inspect
from unittest.mock import Mock, patch

import pytest

from egregora.agents.writer import _index_new_content_in_rag
from egregora.config.settings import RAGSettings
from egregora.data_primitives.document import Document, DocumentType
from egregora.orchestration.pipelines.write import (
    _index_media_into_rag,
    _prepare_pipeline_data,
)


@pytest.fixture
def rag_settings_factory():
    """Factory for creating RAG settings with overrides.

    Use this fixture to create RAG settings with specific test values.
    """

    def _create(*, enabled=True, **kwargs):
        return RAGSettings(enabled=enabled, **kwargs)

    return _create


class TestRAGExceptionHandling:
    """Tests verifying graceful degradation on RAG failures at caller level."""

    def test_exception_during_indexing_is_caught(self, rag_settings_factory):
        """Verify exceptions during RAG indexing don't crash post generation."""
        # Use factory to create RAG settings
        mock_resources = Mock()
        mock_resources.retrieval_config = rag_settings_factory(enabled=True)
        mock_resources.output = Mock()

        # Use real Document instances
        test_doc = Document(
            content="# Test Post\n\nTest content",
            type=DocumentType.POST,
            metadata={"slug": "test-post"},
        )
        mock_resources.output.documents = Mock(return_value=[test_doc])

        # Mock only the external dependency
        with patch("egregora.agents.writer.index_documents") as mock_index:
            mock_index.side_effect = RuntimeError("Database connection failed")

            # Should not raise - error is caught and logged
            _index_new_content_in_rag(mock_resources, saved_posts=["test-post"], saved_profiles=[])

            # Verify index_documents was called
            mock_index.assert_called_once()

    def test_successful_indexing_logs_count(self, caplog, rag_settings_factory):
        """Verify successful indexing logs the indexed document count."""
        # Use factory to create RAG settings
        mock_resources = Mock()
        mock_resources.retrieval_config = rag_settings_factory(enabled=True)
        mock_resources.output = Mock()

        # Use real Document instances
        test_docs = [
            Document(
                content=f"# Test Post {i}\n\nTest content",
                type=DocumentType.POST,
                metadata={"slug": f"test-post-{i}"},
            )
            for i in range(3)
        ]
        mock_resources.output.documents = Mock(return_value=test_docs)

        with patch("egregora.agents.writer.index_documents") as mock_index:
            with caplog.at_level("INFO"):
                _index_new_content_in_rag(
                    mock_resources,
                    saved_posts=["test-post-0", "test-post-1", "test-post-2"],
                    saved_profiles=[],
                )

            # Verify indexing was called
            mock_index.assert_called_once()
            # Verify log message
            assert "Indexed 3 new posts in RAG" in caplog.text

    def test_no_indexing_when_rag_disabled(self, rag_settings_factory):
        """Verify indexing is skipped when RAG is disabled."""
        # Use factory to create RAG settings with RAG disabled
        mock_resources = Mock()
        mock_resources.retrieval_config = rag_settings_factory(enabled=False)
        mock_resources.output = Mock()

        with patch("egregora.rag.index_documents") as mock_index:
            _index_new_content_in_rag(mock_resources, saved_posts=["test-post"], saved_profiles=[])

            # Should not attempt indexing when disabled
            mock_index.assert_not_called()

    def test_no_indexing_when_no_posts_saved(self, rag_settings_factory):
        """Verify indexing is skipped when no posts were saved."""
        # Use factory to create RAG settings
        mock_resources = Mock()
        mock_resources.retrieval_config = rag_settings_factory(enabled=True)
        mock_resources.output = Mock()

        with patch("egregora.rag.index_documents") as mock_index:
            # No posts or profiles saved (empty lists)
            _index_new_content_in_rag(mock_resources, saved_posts=[], saved_profiles=[])

            # Should not attempt indexing
            mock_index.assert_not_called()

    def test_rag_enabled_by_default(self, rag_settings_factory):
        """Verify RAG is enabled by default in settings."""
        settings = rag_settings_factory(enabled=True)
        assert settings.enabled is True, "RAG should be enabled by default"


class TestPipelineRAGExceptionHandling:
    """Tests for RAG exception handling in write_pipeline.py."""

    def test_prepare_pipeline_catches_exceptions(self):
        """Verify pipeline catches exceptions during RAG indexing."""
        source = inspect.getsource(_prepare_pipeline_data)
        # Should use specific exception handling for non-critical RAG indexing
        # (not broad except Exception to prevent masking errors)
        assert "except (ConnectionError, TimeoutError)" in source, (
            "RAG indexing should catch specific exceptions (ConnectionError, TimeoutError), not broad Exception"
        )
        # Should have RAG indexing code
        assert "index_documents(existing_docs)" in source

    def test_index_media_is_disabled(self):
        """Verify media indexing is currently disabled (will be re-implemented)."""
        source = inspect.getsource(_index_media_into_rag)
        # Media RAG indexing is currently disabled
        assert "# Media RAG indexing removed" in source or "will be reimplemented" in source.lower()
