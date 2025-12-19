"""Unit tests for writer orchestrator module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from egregora.agents.writer.orchestrator import (
    WriterDepsParams,
    WriterFinalizationParams,
    _check_writer_cache,
    _finalize_writer_results,
    _index_new_content_in_rag,
    _prepare_writer_dependencies,
    write_posts_for_window,
)
from egregora.config.settings import EgregoraConfig


class TestWriterOrchestrator:
    def test_prepare_writer_dependencies(self):
        params = WriterDepsParams(
            window_start=datetime(2024, 1, 1),
            window_end=datetime(2024, 1, 2),
            resources=MagicMock(),
            model_name="model",
            config=EgregoraConfig(),
        )
        deps = _prepare_writer_dependencies(params)
        assert deps.model_name == "model"
        assert deps.config is not None

    def test_check_writer_cache_hit(self):
        mock_cache = MagicMock()
        mock_cache.should_refresh.return_value = False
        mock_cache.writer.get.return_value = {"posts": ["p1"]}

        result = _check_writer_cache(mock_cache, "sig", "label")
        assert result == {"posts": ["p1"]}

    def test_check_writer_cache_miss(self):
        mock_cache = MagicMock()
        mock_cache.should_refresh.return_value = False
        mock_cache.writer.get.return_value = None

        result = _check_writer_cache(mock_cache, "sig", "label")
        assert result is None

    def test_check_writer_cache_refresh(self):
        mock_cache = MagicMock()
        mock_cache.should_refresh.return_value = True

        result = _check_writer_cache(mock_cache, "sig", "label")
        assert result is None

    @patch("egregora.agents.writer.orchestrator.index_documents")
    def test_index_new_content_in_rag(self, mock_index):
        mock_resources = MagicMock()
        mock_resources.retrieval_config.enabled = True

        mock_doc = MagicMock()
        mock_doc.type = "post" # DocumentType.POST (simplified for mock check)
        # Mocking enum comparison requires care, assuming simple string or object equality
        # In real code it checks DocumentType enum.
        # Let's mock the output format's documents iterator properly.

        from egregora.data_primitives.document import DocumentType, Document

        doc = Document(content="c", type=DocumentType.POST, metadata={"slug": "post1"})
        mock_resources.output.documents.return_value = [doc]

        _index_new_content_in_rag(mock_resources, ["post1"], [])

        mock_index.assert_called_once()

    def test_index_new_content_in_rag_disabled(self):
        mock_resources = MagicMock()
        mock_resources.retrieval_config.enabled = False

        _index_new_content_in_rag(mock_resources, ["p1"], [])
        # Should return early without error or indexing

    @patch("egregora.agents.writer.orchestrator._index_new_content_in_rag")
    def test_finalize_writer_results(self, mock_index):
        params = WriterFinalizationParams(
            saved_posts=["p1"],
            saved_profiles=[],
            resources=MagicMock(),
            deps=MagicMock(),
            cache=MagicMock(),
            signature="sig",
        )

        result = _finalize_writer_results(params)

        assert result["posts"] == ["p1"]
        params.resources.output.finalize_window.assert_called_once()
        params.cache.writer.set.assert_called_once()
        mock_index.assert_called_once()

    @patch("egregora.agents.writer.orchestrator._build_context_and_signature")
    @patch("egregora.agents.writer.orchestrator._check_writer_cache")
    @patch("egregora.agents.writer.orchestrator._prepare_writer_dependencies")
    @patch("egregora.agents.writer.orchestrator._render_writer_prompt")
    @patch("egregora.agents.writer.orchestrator.execute_writer_with_error_handling")
    @patch("egregora.agents.writer.orchestrator._finalize_writer_results")
    def test_write_posts_for_window_full_flow(
        self,
        mock_finalize,
        mock_execute,
        mock_render,
        mock_deps,
        mock_cache,
        mock_context,
    ):
        # Setup
        mock_context.return_value = (MagicMock(), "sig")
        mock_cache.return_value = None  # Cache miss
        mock_deps.return_value = MagicMock()
        mock_render.return_value = "prompt"
        mock_execute.return_value = (["p1"], [])
        mock_finalize.return_value = {"posts": ["p1"], "profiles": []}

        params = MagicMock()
        params.table.count().execute.return_value = 10
        params.config = EgregoraConfig()
        # Use real datetimes for format strings
        params.window_start = datetime(2024, 1, 1)
        params.window_end = datetime(2024, 1, 2)

        result = write_posts_for_window(params)

        assert result["posts"] == ["p1"]
        mock_execute.assert_called_once()
        mock_finalize.assert_called_once()

    def test_write_posts_for_window_empty_table(self):
        params = MagicMock()
        params.table.count().execute.return_value = 0

        result = write_posts_for_window(params)
        assert result["posts"] == []
        assert result["profiles"] == []
