"""Tests for writer_tools module - ensures tool functions are independently testable."""

from unittest.mock import Mock, patch

import pytest
from pydantic_ai import ModelRetry

import egregora.rag as rag_pkg
import egregora.rag.models as rag_models
from egregora.agents.tools import writer_tools
from egregora.agents.tools.writer_tools import (
    AnnotationContext,
    AnnotationResult,
    BannerContext,
    ReadProfileResult,
    ToolContext,
    WritePostResult,
    WriteProfileResult,
    annotate_conversation_impl,
    generate_banner_impl,
    read_profile_impl,
    search_media_impl,
    write_post_impl,
    write_profile_impl,
)
from egregora.data_primitives.document import DocumentType
from egregora.output_sinks.exceptions import DocumentNotFoundError


class TestWriterToolsExtraction:
    """Test that writer tools are properly extracted and independently testable."""

    def test_write_post_impl_creates_document(self):
        """Test write_post_impl creates and persists a post document."""
        # Arrange
        mock_output_sink = Mock()
        ctx = ToolContext(output_sink=mock_output_sink, window_label="2024-11-29")
        metadata = {
            "title": "Test Post",
            "slug": "test-post",
            "date": "2024-11-29",
            "tags": ["test"],
        }
        content = "# Test Content"

        # Act
        result = write_post_impl(ctx, metadata, content)

        # Assert
        assert isinstance(result, WritePostResult)
        assert result.status == "success"
        mock_output_sink.persist.assert_called_once()
        persisted_doc = mock_output_sink.persist.call_args[0][0]
        assert persisted_doc.type == DocumentType.POST
        assert persisted_doc.content == content
        assert persisted_doc.metadata == metadata

    def test_read_profile_impl_returns_content(self):
        """Test read_profile_impl reads profile from output sink."""
        # Arrange
        mock_output_sink = Mock()
        mock_doc = Mock(content="# Profile Content")
        mock_output_sink.get.return_value = mock_doc
        ctx = ToolContext(output_sink=mock_output_sink, window_label="test")

        # Act
        result = read_profile_impl(ctx, "test-uuid")

        # Assert
        assert isinstance(result, ReadProfileResult)
        assert result.content == "# Profile Content"
        mock_output_sink.get.assert_called_once_with(DocumentType.PROFILE, "test-uuid")

    def test_read_profile_impl_handles_missing_profile(self):
        """Test read_profile_impl returns default message for missing profile."""
        # Arrange
        mock_output_sink = Mock()
        mock_output_sink.get.side_effect = DocumentNotFoundError("profile", "missing-uuid")
        ctx = ToolContext(output_sink=mock_output_sink, window_label="test")

        # Act
        result = read_profile_impl(ctx, "missing-uuid")

        # Assert
        assert result.content == "No profile exists yet."

    def test_write_profile_impl_creates_document(self):
        """Test write_profile_impl creates and persists a profile document."""
        # Arrange
        mock_output_sink = Mock()
        ctx = ToolContext(output_sink=mock_output_sink, window_label="2024-11-29")
        content = "# Test Profile"

        # Act
        result = write_profile_impl(ctx, "test-uuid", content)

        # Assert
        assert isinstance(result, WriteProfileResult)
        assert result.status == "success"
        mock_output_sink.persist.assert_called_once()
        persisted_doc = mock_output_sink.persist.call_args[0][0]
        assert persisted_doc.type == DocumentType.PROFILE
        assert persisted_doc.metadata["uuid"] == "test-uuid"

    def test_search_media_impl_handles_rag_errors(self):
        """Test search_media_impl gracefully handles RAG backend errors."""
        # This test verifies error handling works without needing actual RAG backend

        # Patch search to raise an error
        with patch("egregora.agents.tools.writer_tools.search", side_effect=RuntimeError("RAG error")):
            # Act
            with pytest.raises(ModelRetry) as excinfo:
                search_media_impl("test query", top_k=5)

            # Assert - should raise ModelRetry on connection error
            assert "RAG backend unavailable" in str(excinfo.value)

    def test_annotate_conversation_impl_raises_without_store(self):
        """Test annotate_conversation_impl raises error when store is None."""
        # Arrange
        ctx = AnnotationContext(annotations_store=None)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Annotation store is not configured"):
            annotate_conversation_impl(ctx, "parent-id", "message", "test commentary")

    def test_annotate_conversation_impl_saves_annotation(self):
        """Test annotate_conversation_impl saves annotation to store."""
        # Arrange
        mock_store = Mock()

        # Mock a Document-like object that save_annotation would return
        mock_annotation = Mock()
        mock_annotation.document_id = "ann-123"
        mock_annotation.parent_id = "msg-456"
        mock_annotation.metadata = {"parent_type": "message"}

        mock_store.save_annotation.return_value = mock_annotation
        ctx = AnnotationContext(annotations_store=mock_store)

        # Act
        result = annotate_conversation_impl(ctx, "msg-456", "message", "Great point!")

        # Assert
        assert isinstance(result, AnnotationResult)
        assert result.status == "success"
        assert result.annotation_id == "ann-123"
        mock_store.save_annotation.assert_called_once_with(
            parent_id="msg-456", parent_type="message", commentary="Great point!"
        )

    def test_generate_banner_impl_handles_failure(self):
        """Test generate_banner_impl returns failure result when generation fails."""
        # Arrange
        mock_output_sink = Mock()
        ctx = BannerContext(output_sink=mock_output_sink, task_store=None)

        # Mock the generate_banner function to return a failed result
        mock_result = Mock(success=False, error="Banner generation failed", document=None)

        with patch("egregora.agents.tools.writer_tools.generate_banner", return_value=mock_result):
            # Act
            result = generate_banner_impl(ctx, "test-slug", "Test Title", "Test summary")

            # Assert
            assert result.status == "failed"
            assert result.error == "Banner generation failed"
            assert result.path is None
            assert result.image_path is None


class TestToolContexts:
    """Test that context dataclasses provide clean dependency injection."""

    def test_tool_context_creation(self):
        """Test ToolContext can be created with required dependencies."""
        mock_output = Mock()
        ctx = ToolContext(output_sink=mock_output, window_label="test")

        assert ctx.output_sink == mock_output
        assert ctx.window_label == "test"

    def test_annotation_context_creation(self):
        """Test AnnotationContext can be created."""
        mock_store = Mock()
        ctx = AnnotationContext(annotations_store=mock_store)

        assert ctx.annotations_store == mock_store

    def test_banner_context_creation(self):
        """Test BannerContext can be created."""
        mock_output = Mock()
        ctx = BannerContext(output_sink=mock_output)

        assert ctx.output_sink == mock_output


class TestImportFix:
    """Test that RAG imports are correct (regression test for import error fix)."""

    def test_rag_imports_work(self):
        """Test that RAG imports don't raise ModuleNotFoundError."""
        # This test will fail if imports are broken
        # If we get here, imports work
        assert callable(writer_tools.search_media_impl)
        assert callable(rag_pkg.search)
        assert rag_models.RAGQueryRequest is not None
