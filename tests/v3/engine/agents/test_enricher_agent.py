"""Tests for the EnricherAgent."""

from unittest.mock import MagicMock

import pytest

from egregora_v3.core.context import PipelineContext
from egregora_v3.engine.agents.enricher import EnricherAgent, EnrichmentResult


@pytest.mark.asyncio
async def test_enricher_agent_enrich_media_urls():
    """Tests that the EnricherAgent can be called with a list of media URLs."""
    agent = EnricherAgent(model="test")
    media_urls = ["http://example.com/image.jpg", "http://example.com/image2.png"]
    mock_library = MagicMock()
    context = PipelineContext(run_id="test_run", library=mock_library)

    result = await agent.enrich(media_urls, context)

    assert isinstance(result, EnrichmentResult)
    assert "A beautiful sunset" in result.description


@pytest.mark.asyncio
async def test_enricher_agent_handles_empty_list():
    """Tests that the EnricherAgent returns None for an empty list of media URLs."""
    agent = EnricherAgent(model="test")
    media_urls = []
    mock_library = MagicMock()
    context = PipelineContext(run_id="test_run", library=mock_library)

    result = await agent.enrich(media_urls, context)

    assert result is None


@pytest.mark.asyncio
async def test_enricher_agent_uses_test_model():
    """Tests that the EnricherAgent works with the TestModel."""
    agent = EnricherAgent(model="test")
    media_urls = ["http://example.com/image.jpg"]
    context = PipelineContext(run_id="test_run", library=MagicMock())

    result = await agent.enrich(media_urls, context)

    assert isinstance(result, EnrichmentResult)
    assert result.description
