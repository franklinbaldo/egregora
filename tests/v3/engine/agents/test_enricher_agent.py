"""Tests for the EnricherAgent."""

import pytest
from unittest.mock import MagicMock
from egregora_v3.core.context import PipelineContext
from egregora_v3.engine.agents.enricher import EnricherAgent, EnrichmentResult


@pytest.mark.asyncio
async def test_enricher_agent_accepts_media_urls():
    """Tests that the EnricherAgent can be called with a list of media URLs."""
    # Arrange
    agent = EnricherAgent(model="test")
    media_urls = ["http://example.com/image.jpg", "http://example.com/image2.png"]
    # Mock the ContentLibrary
    mock_library = MagicMock()
    context = PipelineContext(run_id="test_run", library=mock_library)

    # Act
    result = await agent.enrich(media_urls, context)

    # Assert
    assert isinstance(result, EnrichmentResult)
    assert (
        result.description
        == "A beautiful sunset over the ocean with orange and pink clouds reflecting on the water."
    )


@pytest.mark.asyncio
async def test_enricher_agent_handles_empty_list():
    """Tests that the EnricherAgent returns None for an empty list of media URLs."""
    # Arrange
    agent = EnricherAgent(model="test")
    media_urls = []
    # Mock the ContentLibrary
    mock_library = MagicMock()
    context = PipelineContext(run_id="test_run", library=mock_library)

    # Act
    result = await agent.enrich(media_urls, context)

    # Assert
    assert result is None
