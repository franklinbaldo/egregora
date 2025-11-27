"""Unit tests for RAG exception handling during post-write indexing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import ibis.common.exceptions


class TestVectorStoreExceptionHandling:
    """Tests verifying VectorStore handles DuckDB errors internally."""

    def test_duckdb_error_handled_internally_by_index_documents(self):
        """Verify DuckDB errors in index_documents() are caught and return 0."""
        from egregora.agents.shared.rag.store import VectorStore

        # Setup mock storage
        mock_storage = Mock()
        mock_storage.get_table_columns.return_value = []
        mock_storage.ibis_conn.list_tables.return_value = []
        mock_storage.execute_sql = Mock()
        mock_conn = Mock()
        mock_conn.execute = Mock()
        mock_storage.connection = Mock(
            return_value=Mock(__enter__=Mock(return_value=mock_conn), __exit__=Mock(return_value=None))
        )
        mock_conn = Mock()
        mock_conn.execute = Mock()
        mock_storage.connection = Mock(
            return_value=Mock(__enter__=Mock(return_value=mock_conn), __exit__=Mock(return_value=None))
        )

        store = VectorStore(Path("/tmp/test.parquet"), storage=mock_storage)

        with patch("egregora.agents.shared.rag.indexing.index_documents_for_rag") as mock_index:
            import duckdb

            mock_index.side_effect = duckdb.Error("VSS extension not loaded")

            # Should return 0, not raise
            result = store.index_documents(Mock(), embedding_model="test-model")
            assert result == 0

    def test_duckdb_error_handled_internally_by_index_media(self):
        """Verify DuckDB errors in index_media() are caught and return 0."""
        from egregora.agents.shared.rag.store import VectorStore

        mock_storage = Mock()
        mock_storage.get_table_columns.return_value = []
        mock_storage.ibis_conn.list_tables.return_value = []
        mock_storage.execute_sql = Mock()
        mock_conn = Mock()
        mock_conn.execute = Mock()
        mock_storage.connection = Mock(
            return_value=Mock(__enter__=Mock(return_value=mock_conn), __exit__=Mock(return_value=None))
        )

        store = VectorStore(Path("/tmp/test.parquet"), storage=mock_storage)

        with patch("egregora.agents.shared.rag.indexing.index_all_media") as mock_index:
            import duckdb

            mock_index.side_effect = duckdb.Error("Locked file")

            # Should return 0, not raise
            result = store.index_media(Path("/tmp/docs"), embedding_model="test-model")
            assert result == 0


class TestRAGExceptionHandling:
    """Tests verifying graceful degradation on RAG failures at caller level."""

    def test_ibis_error_during_indexing_is_caught(self):
        """Verify IbisError during RAG indexing doesn't crash post generation."""
        from egregora.agents.writer import _index_new_content_in_rag

        mock_resources = Mock()
        mock_resources.rag_store = Mock()
        mock_resources.rag_store.index_documents = Mock(
            side_effect=ibis.common.exceptions.IbisError("Table not found")
        )
        mock_resources.output = Mock()
        mock_resources.storage = Mock()
        mock_resources.embedding_model = "test-model"

        # Should not raise
        _index_new_content_in_rag(mock_resources, saved_posts=True, saved_profiles=False)

        mock_resources.rag_store.index_documents.assert_called_once()

    def test_os_error_during_indexing_is_caught(self):
        """Verify OSError (locked files) during RAG indexing doesn't crash."""
        from egregora.agents.writer import _index_new_content_in_rag

        mock_resources = Mock()
        mock_resources.rag_store = Mock()
        mock_resources.rag_store.index_documents = Mock(
            side_effect=OSError("Permission denied: chunks.parquet")
        )
        mock_resources.output = Mock()
        mock_resources.storage = Mock()
        mock_resources.embedding_model = "test-model"

        # Should not raise
        _index_new_content_in_rag(mock_resources, saved_posts=True, saved_profiles=False)

        mock_resources.rag_store.index_documents.assert_called_once()

    def test_successful_indexing_logs_count(self, caplog):
        """Verify successful indexing logs the indexed document count."""
        from egregora.agents.writer import _index_new_content_in_rag

        mock_resources = Mock()
        mock_resources.rag_store = Mock()
        mock_resources.rag_store.index_documents = Mock(return_value=5)
        mock_resources.output = Mock()
        mock_resources.storage = Mock()
        mock_resources.embedding_model = "test-model"

        with caplog.at_level("INFO"):
            _index_new_content_in_rag(mock_resources, saved_posts=True, saved_profiles=False)

        assert "Indexed 5 new/changed documents" in caplog.text

    def test_no_indexing_when_no_posts_saved(self):
        """Verify indexing is skipped when no posts were saved."""
        from egregora.agents.writer import _index_new_content_in_rag

        mock_resources = Mock()
        mock_resources.rag_store = Mock()
        mock_resources.output = Mock()
        mock_resources.storage = Mock()

        # No posts or profiles saved
        _index_new_content_in_rag(mock_resources, saved_posts=False, saved_profiles=False)

        # Should not attempt indexing
        mock_resources.rag_store.index_documents.assert_not_called()


class TestPipelineRAGExceptionHandling:
    """Tests for RAG exception handling in write_pipeline.py."""

    def test_prepare_pipeline_does_not_leak_duckdb(self):
        """Verify DuckDB is not imported or caught in pipeline code."""
        import inspect

        from egregora.orchestration.write_pipeline import _prepare_pipeline_data

        source = inspect.getsource(_prepare_pipeline_data)
        # DuckDB should NOT be in exception handling - it's handled internally
        assert "duckdb.Error" not in source
        # Should only catch Ibis and OS errors
        assert "ibis.common.exceptions.IbisError" in source
        assert "OSError" in source

    def test_index_media_does_not_leak_duckdb(self):
        """Verify DuckDB is not imported or caught in media indexing."""
        import inspect

        from egregora.orchestration.write_pipeline import _index_media_into_rag

        source = inspect.getsource(_index_media_into_rag)
        # DuckDB should NOT be in exception handling
        assert "duckdb.Error" not in source
        assert "ibis.common.exceptions.IbisError" in source
        assert "OSError" in source
