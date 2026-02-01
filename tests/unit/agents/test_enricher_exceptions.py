from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as api_exceptions

from egregora.agents.enricher import EnrichmentWorker


@pytest.fixture
def mock_context():
    """Provides a mocked PipelineContext for the EnrichmentWorker."""
    context = MagicMock()
    context.config.models.enricher_vision = "gemini-pro-vision"
    context.config.enrichment.strategy = "not_batch_all"  # to ensure we hit the part with GoogleBatchModel
    context.input_path = None
    return context


@pytest.mark.parametrize(
    "exception_to_raise",
    [
        api_exceptions.ResourceExhausted("Quota exceeded"),
        api_exceptions.InternalServerError("Internal error"),
        api_exceptions.ServiceUnavailable("Service unavailable"),
        api_exceptions.GatewayTimeout("Gateway timeout"),
    ],
)
@patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
def test_execute_media_batch_fallback_on_api_errors(exception_to_raise, mock_context):
    """
    Verify that _execute_media_batch falls back to individual calls
    when a specific API error is raised from the batch call.
    """
    # Arrange
    worker = EnrichmentWorker(ctx=mock_context)
    requests = [{"tag": "task1", "contents": ["image_data"]}]
    task_map = {"task1": {"_parsed_payload": {"filename": "image.jpg"}}}

    mock_model_instance = MagicMock()
    # Configure the mock to raise the exception when run_batch is called
    mock_model_instance.run_batch.side_effect = exception_to_raise

    # Mock the individual call method to verify it's called
    worker.media_handler._execute_individual = MagicMock(return_value=[])

    # Act
    with patch("egregora.agents.enricher.media.GoogleBatchModel", return_value=mock_model_instance):
        worker.media_handler._execute_batch(requests, task_map)

    # Assert
    worker.media_handler._execute_individual.assert_called_once_with(
        requests, task_map, "gemini-pro-vision", "test-key"
    )
