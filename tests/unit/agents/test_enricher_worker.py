import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

from egregora.agents.enricher import EnrichmentWorker


@pytest.fixture
def mock_context(config_factory):
    """Provides a mock PipelineContext for the EnrichmentWorker."""
    ctx = MagicMock()
    ctx.config = config_factory()
    # Configure required nested properties for the media batch code path
    ctx.config.models.enricher_vision = "gemini-pro-vision"
    ctx.config.enrichment.strategy = "batch_all"

    # The code path requires an API key from the environment
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
        yield ctx


def test_media_batch_usage_limit_fallback(mock_context):
    """
    Verify that _execute_media_batch falls back to individual calls
    when GoogleBatchModel.run_batch raises UsageLimitExceeded.
    """
    # Override strategy to test standard batch API path
    mock_context.config.enrichment.strategy = "individual"

    worker = EnrichmentWorker(ctx=mock_context)
    requests = [{"tag": "1"}, {"tag": "2"}]
    task_map = {"1": {}, "2": {}}

    with (
        patch("egregora.agents.enricher.media.GoogleBatchModel") as mock_batch_model,
        patch.object(worker.media_handler, "_execute_individual", return_value=[]) as mock_fallback,
    ):
        # Configure the mock to raise the specific exception
        mock_batch_model.return_value.run_batch.side_effect = UsageLimitExceeded("Quota exceeded")

        # Execute the method
        worker.media_handler._execute_batch(requests, task_map)

        # Assert that the fallback method was called
        mock_fallback.assert_called_once()


def test_enrichment_worker_disabled_returns_zero(mock_context):
    """
    Verify that the EnrichmentWorker.run() method returns 0 immediately
    if enrichment is disabled in the configuration.
    """
    # Disable enrichment in the mock configuration
    mock_context.config.enrichment.enabled = False

    worker = EnrichmentWorker(ctx=mock_context)

    # Mock the task store to ensure it's not called
    with patch.object(worker, "task_store", MagicMock()) as mock_task_store:
        mock_task_store.fetch_pending.return_value = []

        # Execute the run method
        result = worker.run()

        # Assert that the method returned 0 and did not fetch tasks
        assert result == 0
        mock_task_store.fetch_pending.assert_not_called()


def test_media_batch_http_error_fallback(mock_context):
    """
    Verify that _execute_media_batch falls back to individual calls
    when GoogleBatchModel.run_batch raises ModelHTTPError.
    """
    # Override strategy to test standard batch API path
    mock_context.config.enrichment.strategy = "individual"

    worker = EnrichmentWorker(ctx=mock_context)
    requests = [{"tag": "1"}, {"tag": "2"}]
    task_map = {"1": {}, "2": {}}

    with (
        patch("egregora.agents.enricher.media.GoogleBatchModel") as mock_batch_model,
        patch.object(worker.media_handler, "_execute_individual", return_value=[]) as mock_fallback,
    ):
        # Configure the mock to raise the specific exception
        mock_batch_model.return_value.run_batch.side_effect = ModelHTTPError(
            status_code=500, model_name="test", body="Server error"
        )

        # Execute the method
        worker.media_handler._execute_batch(requests, task_map)

        # Assert that the fallback method was called
        mock_fallback.assert_called_once()
