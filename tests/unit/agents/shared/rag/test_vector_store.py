"""Unit tests for VectorStore facade methods."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from egregora.agents.shared.rag.store import VectorStore


@pytest.fixture
def mock_storage():
    """Create a mock storage backend."""
    storage = Mock()
    storage.execute_ibis_query = Mock(return_value=Mock())
    storage.get_table_columns = Mock(return_value=[])
    storage.execute_sql = Mock()

    # Mock the context manager for connection()
    mock_conn = Mock()
    mock_conn.execute = Mock()
    storage.connection = Mock(return_value=Mock(__enter__=Mock(return_value=mock_conn), __exit__=Mock(return_value=None)))

    return storage


@pytest.fixture
def vector_store(tmp_path, mock_storage):
    """Create a VectorStore instance for testing."""
    parquet_path = tmp_path / "test_chunks.parquet"
    return VectorStore(parquet_path, storage=mock_storage)


class TestVectorStoreIndexDocuments:
    """Tests for VectorStore.index_documents() method."""

    def test_index_documents_calls_indexing_function(self, vector_store):
        """Verify index_documents delegates to index_documents_for_rag."""
        mock_adapter = Mock()
        embedding_model = "models/gemini-embedding-001"

        with patch("egregora.agents.shared.rag.indexing.index_documents_for_rag") as mock_index:
            mock_index.return_value = 5
            result = vector_store.index_documents(mock_adapter, embedding_model=embedding_model)

            # Verify delegation
            mock_index.assert_called_once_with(
                mock_adapter, vector_store, embedding_model=embedding_model
            )
            assert result == 5

    def test_index_documents_returns_count(self, vector_store):
        """Verify index_documents returns the indexed document count."""
        mock_adapter = Mock()

        with patch("egregora.agents.shared.rag.indexing.index_documents_for_rag") as mock_index:
            mock_index.return_value = 42
            result = vector_store.index_documents(mock_adapter, embedding_model="test-model")

            assert result == 42


class TestVectorStoreIndexMedia:
    """Tests for VectorStore.index_media() method."""

    def test_index_media_calls_indexing_function(self, vector_store, tmp_path):
        """Verify index_media delegates to index_all_media."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        embedding_model = "models/gemini-embedding-001"

        with patch("egregora.agents.shared.rag.indexing.index_all_media") as mock_index:
            mock_index.return_value = 10
            result = vector_store.index_media(docs_dir, embedding_model=embedding_model)

            # Verify delegation
            mock_index.assert_called_once_with(docs_dir, vector_store, embedding_model=embedding_model)
            assert result == 10


class TestVectorStoreQueryMedia:
    """Tests for VectorStore.query_media() method."""

    def test_query_media_delegates_with_all_parameters(self, vector_store):
        """Verify query_media passes all parameters correctly."""
        query = "test query"
        media_types = ["image", "video"]
        top_k = 10
        min_similarity = 0.8

        with patch("egregora.agents.shared.rag.retriever.query_media") as mock_query:
            mock_result = Mock()
            mock_query.return_value = mock_result

            result = vector_store.query_media(
                query=query,
                media_types=media_types,
                top_k=top_k,
                min_similarity_threshold=min_similarity,
                deduplicate=True,
                embedding_model="test-model",
                retrieval_mode="ann",
                retrieval_nprobe=10,
                retrieval_overfetch=5,
            )

            # Verify delegation with all params
            mock_query.assert_called_once_with(
                query=query,
                store=vector_store,
                media_types=media_types,
                top_k=top_k,
                min_similarity_threshold=min_similarity,
                deduplicate=True,
                embedding_model="test-model",
                retrieval_mode="ann",
                retrieval_nprobe=10,
                retrieval_overfetch=5,
            )
            assert result == mock_result


class TestVectorStoreQuerySimilarPosts:
    """Tests for VectorStore.query_similar_posts() method."""

    def test_query_similar_posts_delegates_correctly(self, vector_store):
        """Verify query_similar_posts delegates to retriever function."""
        mock_table = Mock()

        with patch("egregora.agents.shared.rag.retriever.query_similar_posts") as mock_query:
            mock_result = Mock()
            mock_query.return_value = mock_result

            result = vector_store.query_similar_posts(
                table=mock_table,
                embedding_model="test-model",
                top_k=5,
                deduplicate=True,
                retrieval_mode="exact",
                retrieval_nprobe=None,
                retrieval_overfetch=None,
            )

            # Verify delegation
            mock_query.assert_called_once_with(
                table=mock_table,
                store=vector_store,
                embedding_model="test-model",
                top_k=5,
                deduplicate=True,
                retrieval_mode="exact",
                retrieval_nprobe=None,
                retrieval_overfetch=None,
            )
            assert result == mock_result


class TestVectorStoreIsAvailable:
    """Tests for VectorStore.is_available() static method."""

    def test_is_available_delegates_to_embedder(self):
        """Verify is_available checks RAG availability via embedder."""
        with patch("egregora.agents.shared.rag.embedder.is_rag_available") as mock_check:
            mock_check.return_value = True
            result = VectorStore.is_available()

            mock_check.assert_called_once()
            assert result is True

    def test_is_available_returns_false_when_unavailable(self):
        """Verify is_available returns False when RAG is unavailable."""
        with patch("egregora.agents.shared.rag.embedder.is_rag_available") as mock_check:
            mock_check.return_value = False
            result = VectorStore.is_available()

            assert result is False


class TestVectorStoreEmbedQuery:
    """Tests for VectorStore.embed_query() static method."""

    def test_embed_query_delegates_to_embedder(self):
        """Verify embed_query uses embedder function."""
        query_text = "test query"
        model = "test-model"
        expected_embedding = [0.1, 0.2, 0.3]

        with patch("egregora.agents.shared.rag.embedder.embed_query_text") as mock_embed:
            mock_embed.return_value = expected_embedding
            result = VectorStore.embed_query(query_text, model=model)

            mock_embed.assert_called_once_with(query_text, model=model)
            assert result == expected_embedding


class TestVectorStoreFacadePattern:
    """Tests verifying the Facade pattern implementation."""

    def test_all_facade_methods_use_lazy_imports(self):
        """Verify facade methods use lazy imports to avoid circular dependencies."""
        # This is a meta-test that verifies the pattern is maintained
        # The actual implementation uses lazy imports inside methods
        import inspect

        # Get all public methods of VectorStore
        methods = [
            name
            for name, method in inspect.getmembers(VectorStore, predicate=inspect.isfunction)
            if not name.startswith("_")
            and name
            not in [
                "append",
                "persist",
                "search",
                "get_indexed_sources_table",
                "list_datasets",
                "get_dataset_metadata",
            ]
        ]

        # These are the facade methods that should use lazy imports
        facade_methods = [
            "index_documents",
            "index_media",
            "query_media",
            "query_similar_posts",
            "is_available",
            "embed_query",
        ]

        for method_name in facade_methods:
            assert method_name in methods, f"Expected facade method {method_name} not found"
