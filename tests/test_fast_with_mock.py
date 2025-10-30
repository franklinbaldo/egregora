"""Fast tests using MockGeminiBatchClient (no real API calls).

These tests validate the pipeline works correctly with mocked batch clients.
They should run in seconds instead of minutes.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_pipeline_with_mock_batch_client(
    whatsapp_fixture,
    mock_batch_client,
    tmp_path: Path,
):
    """Test that pipeline runs quickly with mocked batch client.

    This test should complete in seconds, not minutes, because all
    batch API calls are mocked.
    """
    from egregora.orchestration.pipeline import process_whatsapp_export

    output_dir = tmp_path / "site"
    output_dir.mkdir()

    # Create mkdocs.yml for site structure
    mkdocs_yml = output_dir / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test Site\ndocs_dir: docs\n", encoding="utf-8")

    docs_dir = output_dir / "docs"
    docs_dir.mkdir()

    # Run pipeline with mocked batch client (should be fast!)
    # Note: gemini_api_key is just "test-key" from fixture, not real
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        period="day",
        enable_enrichment=False,  # Keep it simple for now
        gemini_api_key="test-key",  # Doesn't matter, using mocks
    )

    # Verify basic output structure was created
    posts_dir = docs_dir / "posts"
    assert posts_dir.exists(), "Posts directory should be created"

    profiles_dir = docs_dir / "profiles"
    assert profiles_dir.exists(), "Profiles directory should be created"

    # NOTE: Post generation may fail with mock LLM responses
    # The important thing is that the pipeline runs FAST (seconds not minutes)
    # Full validation of output content will be done with golden fixtures


def test_mock_embeddings_are_deterministic(mock_batch_client):
    """Verify that mock embeddings are deterministic (same text = same vector)."""
    from tests.mock_batch_client import create_mock_batch_client
    from egregora.utils.batch import EmbeddingBatchRequest

    client = create_mock_batch_client()

    # Generate embeddings twice for same text
    requests = [EmbeddingBatchRequest(text="test text", tag="1")]

    results1 = client.embed_content(requests)
    results2 = client.embed_content(requests)

    # Should be identical (deterministic)
    assert results1[0].embedding == results2[0].embedding
    assert results1[0].embedding is not None
    assert len(results1[0].embedding) == 3072  # Default dimensionality


def test_mock_embeddings_different_for_different_text(mock_batch_client):
    """Verify that different texts produce different embeddings."""
    from tests.mock_batch_client import create_mock_batch_client
    from egregora.utils.batch import EmbeddingBatchRequest

    client = create_mock_batch_client()

    requests = [
        EmbeddingBatchRequest(text="text A", tag="1"),
        EmbeddingBatchRequest(text="text B", tag="2"),
    ]

    results = client.embed_content(requests)

    # Different texts should produce different embeddings
    assert results[0].embedding != results[1].embedding
