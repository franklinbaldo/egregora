import os
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.enricher import EnrichmentWorker
from egregora.agents.exceptions import EnrichmentExecutionError


@pytest.fixture
def mock_context(config_factory):
    """Provides a mock PipelineContext for the EnrichmentWorker."""
    ctx = MagicMock()
    ctx.config = config_factory()
    # Ensure required model config is present
    ctx.config.models.enricher = "gemini-pro"

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
        yield ctx


def test_enrich_single_url_raises_exception(mock_context):
    """
    Verify that _enrich_single_url raises EnrichmentExecutionError
    instead of returning a failure tuple when the agent fails.
    """
    worker = EnrichmentWorker(ctx=mock_context)

    task_data = {"task": {"task_id": "test-task"}, "url": "https://example.com", "prompt": "Test prompt"}

    # Patch the Agent class to raise an exception when instantiated or run
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    with patch("egregora.agents.enricher.Agent") as mock_agent_cls:
        mock_agent_instance = mock_agent_cls.return_value
=======
    with patch("egregora.agents.enricher.Agent") as mock_agent:
        mock_agent_instance = mock_agent.return_value
>>>>>>> origin/pr/2893
=======
    with patch("egregora.agents.enricher.Agent") as mock_agent_class:
        mock_agent_instance = mock_agent_class.return_value
>>>>>>> origin/pr/2890
=======
    with patch("egregora.agents.enricher.Agent") as mock_agent_class:
        mock_agent_instance = mock_agent_class.return_value
>>>>>>> origin/pr/2888
=======
    with patch("egregora.agents.enricher.Agent") as mock_agent_class:
        mock_agent_instance = mock_agent_class.return_value
>>>>>>> origin/pr/2881
=======
    with patch("egregora.agents.enricher.Agent") as mock_agent_cls:
        mock_agent_instance = mock_agent_cls.return_value
>>>>>>> origin/pr/2879
        # Mock the run method to raise a generic exception
        # Note: _enrich_single_url creates an event loop and runs this async,
        # but since we are mocking the sync Agent class wrapper (or pydantic_ai.Agent),
        # we need to be careful. The code does:
        # agent = Agent(...)
        # ...
        # await agent.run(prompt)

        # We need to make the async run method fail.
        async def async_raise(*args, **kwargs):
            msg = "Something went wrong inside the agent"
            raise ValueError(msg)

        mock_agent_instance.run.side_effect = async_raise

        # CURRENT BEHAVIOR: This returns (task, None, error_str)
        # DESIRED BEHAVIOR: This raises EnrichmentExecutionError

        # This assertion expects the DESIRED behavior, so it should FAIL (RED)
        with pytest.raises(EnrichmentExecutionError):
            worker._enrich_single_url(task_data)

        # Verify the cause was preserved (if we were passing)
        # assert "Something went wrong inside the agent" in str(exc_info.value.__cause__)
