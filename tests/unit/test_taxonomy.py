"""Unit tests for taxonomy generation logic."""
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.ops.taxonomy import generate_semantic_taxonomy

@pytest.fixture(autouse=True)
def _ibis_backend():
    """Override global fixture to avoid Ibis connection issues in unit tests."""
    yield

# Mock dependencies
@pytest.fixture
def mock_output_sink():
    sink = MagicMock()
    # Create some dummy documents
    docs = []
    for i in range(10):
        docs.append(Document(
            content=f"Content {i}",
            type=DocumentType.POST,
            metadata={
                "title": f"Post {i}",
                "summary": f"Summary {i}",
                "tags": ["original"],
                "path": f"posts/post_{i}.md"
            }
        ))
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
    vectors = np.random.rand(10, 768)
    backend.get_all_post_vectors = AsyncMock(return_value=(doc_ids, vectors))
    return backend

@pytest.mark.asyncio
async def test_generate_semantic_taxonomy_insufficient_docs(mock_output_sink, mock_config):
    """Test early exit when not enough documents."""
    with patch("egregora.ops.taxonomy.get_backend") as mock_get_backend:
        backend = MagicMock()
        backend.get_all_post_vectors = AsyncMock(return_value=(["1", "2"], np.random.rand(2, 768)))
        mock_get_backend.return_value = backend

        count = await generate_semantic_taxonomy(mock_output_sink, mock_config)
        assert count == 0

@pytest.mark.asyncio
async def test_generate_semantic_taxonomy_success(mock_output_sink, mock_config):
    """Test successful global taxonomy generation."""
    with patch("egregora.ops.taxonomy.get_backend") as mock_get_backend, \
         patch("egregora.ops.taxonomy.create_global_taxonomy_agent") as mock_create_agent:

        # Setup Backend
        backend = MagicMock()
        # Create matching doc IDs
        real_docs = list(mock_output_sink.documents())
        doc_ids = [d.document_id for d in real_docs]
        vectors = np.random.rand(len(doc_ids), 10) # 10-dim vectors
        backend.get_all_post_vectors = AsyncMock(return_value=(doc_ids, vectors))
        mock_get_backend.return_value = backend

        # Setup Agent
        mock_agent = MagicMock()
        mock_result = MagicMock()

        # Mocking GlobalTaxonomyResult structure
        # We need a list of ClusterTags objects
        from egregora.agents.taxonomy import ClusterTags

        # Assume clustering creates 2 clusters (k=sqrt(10/2) -> sqrt(5) -> 2)
        # We'll return mappings for cluster 0 and 1
        mappings = [
            ClusterTags(cluster_id=0, tags=["GlobalTagA", "GlobalTagB"]),
            ClusterTags(cluster_id=1, tags=["GlobalTagC", "GlobalTagD"]),
        ]

        mock_result.data.mappings = mappings
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_create_agent.return_value = mock_agent

        # Run
        count = await generate_semantic_taxonomy(mock_output_sink, mock_config)

        # Verify
        assert count > 0 # Should update docs
        assert mock_output_sink.persist.called

        # Check that persist was called with updated tags
        # We can inspect one of the calls
        args, _ = mock_output_sink.persist.call_args
        doc = args[0]
        # It should have either (TagA, TagB) or (TagC, TagD) plus "original"
        tags = doc.metadata["tags"]
        assert "original" in tags
        assert any(t in tags for t in ["GlobalTagA", "GlobalTagB", "GlobalTagC", "GlobalTagD"])

@pytest.mark.asyncio
async def test_generate_semantic_taxonomy_agent_failure(mock_output_sink, mock_config):
    """Test graceful failure if agent errors out."""
    with patch("egregora.ops.taxonomy.get_backend") as mock_get_backend, \
         patch("egregora.ops.taxonomy.create_global_taxonomy_agent") as mock_create_agent:

        # Setup Backend
        backend = MagicMock()
        real_docs = list(mock_output_sink.documents())
        doc_ids = [d.document_id for d in real_docs]
        vectors = np.random.rand(len(doc_ids), 10)
        backend.get_all_post_vectors = AsyncMock(return_value=(doc_ids, vectors))
        mock_get_backend.return_value = backend

        # Setup Agent to fail
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("API Error"))
        mock_create_agent.return_value = mock_agent

        # Run
        count = await generate_semantic_taxonomy(mock_output_sink, mock_config)

        # Verify
        assert count == 0
