"""Unit tests for taxonomy generation logic."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.ops.taxonomy import generate_semantic_taxonomy


@pytest.fixture(autouse=True)
def _ibis_backend():
    """Override global fixture to avoid Ibis connection issues in unit tests."""
    return


# Mock dependencies
@pytest.fixture
def mock_output_sink():
    sink = MagicMock()
    # Create some dummy documents
    docs = [
        Document(
            content=f"Content {i}",
            type=DocumentType.POST,
            metadata={
                "title": f"Post {i}",
                "summary": f"Summary {i}",
                "tags": ["original"],
                "path": f"posts/post_{i}.md",
            },
        )
        for i in range(10)
    ]
    sink.documents.return_value = docs
    return sink


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.models.writer = "mock-model"
    return config


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    # Return 10 doc IDs and random vectors
    doc_ids = [f"post_{i}" for i in range(10)]
    rng = np.random.default_rng(seed=42)
    vectors = rng.random((10, 768))
    backend.get_all_post_vectors = MagicMock(return_value=(doc_ids, vectors))
    return backend


def test_generate_semantic_taxonomy_insufficient_docs(mock_output_sink, mock_config):
    """Test early exit when not enough documents."""
    with patch("egregora.ops.taxonomy.get_backend") as mock_get_backend:
        backend = MagicMock()
        rng = np.random.default_rng(seed=42)
        backend.get_all_post_vectors = MagicMock(return_value=(["1", "2"], rng.random((2, 768))))
        mock_get_backend.return_value = backend

        count = generate_semantic_taxonomy(mock_output_sink, mock_config)
        assert count == 0


def test_generate_semantic_taxonomy_success(mock_output_sink, mock_config):
    """Test successful global taxonomy generation."""
    with (
        patch("egregora.ops.taxonomy.get_backend") as mock_get_backend,
        patch("egregora.ops.taxonomy.create_global_taxonomy_agent") as mock_create_agent,
    ):
        # Setup Backend
        backend = MagicMock()
        real_docs = list(mock_output_sink.documents())
        doc_ids = [d.document_id for d in real_docs]
        rng = np.random.default_rng(seed=42)
        vectors = rng.random((len(doc_ids), 10))
        backend.get_all_post_vectors = MagicMock(return_value=(doc_ids, vectors))
        mock_get_backend.return_value = backend

        # Setup Agent
        mock_agent = MagicMock()
        mock_result = MagicMock()

        from egregora.agents.taxonomy import ClusterTags

        mappings = [
            ClusterTags(cluster_id=0, tags=["GlobalTagA", "GlobalTagB"]),
            ClusterTags(cluster_id=1, tags=["GlobalTagC", "GlobalTagD"]),
        ]

        mock_result.data.mappings = mappings
        mock_agent.run_sync = MagicMock(return_value=mock_result)
        mock_create_agent.return_value = mock_agent

        # Run
        count = generate_semantic_taxonomy(mock_output_sink, mock_config)

        # Verify
        assert count > 0
        assert mock_output_sink.persist.called


def test_generate_semantic_taxonomy_batching(mock_output_sink, mock_config):
    """Test that large inputs are batched."""
    with (
        patch("egregora.ops.taxonomy.get_backend") as mock_get_backend,
        patch("egregora.ops.taxonomy.create_global_taxonomy_agent") as mock_create_agent,
        patch("egregora.ops.taxonomy.MAX_PROMPT_CHARS", 100),
    ):  # FORCE tiny limit
        # Setup Backend
        backend = MagicMock()
        real_docs = list(mock_output_sink.documents())
        doc_ids = [d.document_id for d in real_docs]
        rng = np.random.default_rng(seed=42)
        vectors = rng.random((len(doc_ids), 10))
        backend.get_all_post_vectors = MagicMock(return_value=(doc_ids, vectors))
        mock_get_backend.return_value = backend

        # Setup Agent
        mock_agent = MagicMock()
        mock_result = MagicMock()

        # Agent will be called multiple times.
        # We simulate it returning empty mappings for simplicity of this test
        # (we just want to verify batching logic triggers multiple calls)
        mock_result.data.mappings = []
        mock_agent.run_sync = MagicMock(return_value=mock_result)
        mock_create_agent.return_value = mock_agent

        # Run
        generate_semantic_taxonomy(mock_output_sink, mock_config)

        # Verify
        # With MAX_PROMPT_CHARS=100, and 10 documents / ~2 clusters,
        # the input strings will definitely exceed 100 chars, forcing >1 batch.
        assert mock_agent.run_sync.call_count >= 2


def test_generate_semantic_taxonomy_agent_failure(mock_output_sink, mock_config):
    """Test graceful failure if agent errors out."""
    with (
        patch("egregora.ops.taxonomy.get_backend") as mock_get_backend,
        patch("egregora.ops.taxonomy.create_global_taxonomy_agent") as mock_create_agent,
    ):
        backend = MagicMock()
        real_docs = list(mock_output_sink.documents())
        doc_ids = [d.document_id for d in real_docs]
        rng = np.random.default_rng(seed=42)
        vectors = rng.random((len(doc_ids), 10))
        backend.get_all_post_vectors = MagicMock(return_value=(doc_ids, vectors))
        mock_get_backend.return_value = backend

        mock_agent = MagicMock()
        mock_agent.run_sync = MagicMock(side_effect=Exception("API Error"))
        mock_create_agent.return_value = mock_agent

        count = generate_semantic_taxonomy(mock_output_sink, mock_config)
        assert count == 0
