"""Tests for mock infrastructure used in other tests.

These tests validate that our mock batch clients behave correctly and
produce deterministic results. This is important for other tests that
rely on the mocks.

Note: Pipeline-level tests have been moved to test_with_golden_fixtures.py
which uses VCR to replay real API responses, providing better integration testing.
"""

from __future__ import annotations

from tests.utils.mock_batch_client import create_mock_batch_client

from egregora.utils.batch import EmbeddingBatchRequest

# Default embedding dimensionality for testing
DEFAULT_EMBEDDING_DIM = 3072


def test_mock_embeddings_are_deterministic(mock_batch_client):
    """Verify that mock embeddings are deterministic (same text = same vector)."""
    client = create_mock_batch_client()

    # Generate embeddings twice for same text
    requests = [EmbeddingBatchRequest(text="test text", tag="1")]

    results1 = client.embed_content(requests)
    results2 = client.embed_content(requests)

    # Should be identical (deterministic)
    assert results1[0].embedding == results2[0].embedding
    assert results1[0].embedding is not None
    assert len(results1[0].embedding) == DEFAULT_EMBEDDING_DIM


def test_mock_embeddings_different_for_different_text(mock_batch_client):
    """Verify that different texts produce different embeddings."""
    client = create_mock_batch_client()

    requests = [
        EmbeddingBatchRequest(text="text A", tag="1"),
        EmbeddingBatchRequest(text="text B", tag="2"),
    ]

    results = client.embed_content(requests)

    # Different texts should produce different embeddings
    assert results[0].embedding != results[1].embedding
