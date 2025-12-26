"""Tests for the EnricherAgent."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from pydantic_ai import Agent

from egregora_v3.core.context import PipelineContext
from egregora_v3.engine.agents.enricher import EnricherAgent, EnrichmentResult


from pydantic_ai.models.test import TestModel


@pytest.fixture
def mock_pydantic_agent() -> Agent:
    """Fixture to create a mock pydantic_ai.Agent with a TestModel."""
    valid_enrichment_dict = {
        "description": "A beautiful sunset over the ocean with orange and pink clouds reflecting on the water.",
        "confidence": 0.95,
        "metadata": {"scene": "sunset", "location": "beach"},
    }
    model_instance = TestModel(custom_output_args=valid_enrichment_dict)
    return Agent(model=model_instance, output_type=EnrichmentResult)


@pytest.mark.asyncio
async def test_enricher_agent_accepts_media_urls(mock_pydantic_agent):
    """Tests that the EnricherAgent can be called with a list of media URLs."""
    # Arrange
    agent = EnricherAgent(agent=mock_pydantic_agent)
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
async def test_enricher_agent_handles_empty_list(mock_pydantic_agent):
    """Tests that the EnricherAgent returns None for an empty list of media URLs."""
    # Arrange
    agent = EnricherAgent(agent=mock_pydantic_agent)
    media_urls = []
    # Mock the ContentLibrary
    mock_library = MagicMock()
    context = PipelineContext(run_id="test_run", library=mock_library)

    # Act
    result = await agent.enrich(media_urls, context)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_enricher_agent_accepts_pydantic_agent():
    """Tests that the EnricherAgent can be instantiated with a pydantic_ai.Agent."""
    # Arrange
    mock_pydantic_agent = MagicMock(spec=Agent)
    mock_pydantic_agent.run = AsyncMock(
        return_value=MagicMock(
            output=EnrichmentResult(description="mocked", confidence=1.0)
        )
    )
    agent = EnricherAgent(agent=mock_pydantic_agent)
    media_urls = ["http://example.com/image.jpg"]
    context = PipelineContext(run_id="test_run", library=MagicMock())

    # Act
    result = await agent.enrich(media_urls, context)

    # Assert
    assert isinstance(result, EnrichmentResult)
    assert result.description == "mocked"
    mock_pydantic_agent.run.assert_awaited_once()
