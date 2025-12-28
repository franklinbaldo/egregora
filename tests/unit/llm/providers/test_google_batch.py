"""Unit tests for the GoogleBatchModel LLM provider."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from egregora.llm.exceptions import (
    BatchJobFailedError,
    BatchJobTimeoutError,
    BatchResultDownloadError,
    InvalidLLMResponseError,
)
from egregora.llm.providers.google_batch import GoogleBatchModel


class TestGoogleBatchModel:
    """Tests for the GoogleBatchModel."""

    @pytest.fixture
    def model(self) -> GoogleBatchModel:
        """Fixture for GoogleBatchModel."""
        return GoogleBatchModel(api_key="test-key", model_name="gemini-1.5-flash")

    def test_poll_job_raises_batch_job_failed_on_failure_state(self, model: GoogleBatchModel):
        """
        GIVEN a batch job that completes with a 'FAILED' state
        WHEN _poll_job is called
        THEN it should raise a BatchJobFailedError
        """
        mock_client = MagicMock()
        mock_job = MagicMock()
        mock_job.state.name = "FAILED"
        # The actual error object is not a dict, but a protobuf message.
        # We mock its structure.
        mock_job.error.code = 500
        mock_job.error.message = "Internal error"
        mock_client.batches.get.return_value = mock_job

        # Temporarily disable the tenacity retry for this test to fail fast
        with patch("tenacity.retry", lambda **kwargs: lambda f: f):
            with pytest.raises(BatchJobFailedError) as exc_info:
                model._poll_job(mock_client, "test-job")

        assert "Batch job failed" in str(exc_info.value)
        assert exc_info.value.job_name == "test-job"
        assert exc_info.value.error_payload.code == 500

    def test_poll_job_raises_batch_job_timeout_on_retry_error(self, model: GoogleBatchModel):
        """
        GIVEN a batch job that times out during polling
        WHEN _poll_job is called
        THEN it should raise a BatchJobTimeoutError
        """
        # Set a very short timeout for the test
        model.timeout = 0.1
        model.poll_interval = 0.05

        mock_client = MagicMock()
        mock_processing_job = MagicMock()
        mock_processing_job.state.name = "PROCESSING"
        mock_client.batches.get.return_value = mock_processing_job

        with pytest.raises(BatchJobTimeoutError) as exc_info:
            model._poll_job(mock_client, "test-job-timeout")

        assert "Batch job polling timed out" in str(exc_info.value)
        assert exc_info.value.job_name == "test-job-timeout"

    def test_download_results_raises_download_error_on_http_error(self, model: GoogleBatchModel):
        """
        GIVEN an HTTP error during result download
        WHEN _download_results is called
        THEN it should raise a BatchResultDownloadError
        """
        mock_client = MagicMock()
        with (
            patch(
                "httpx.Client.get",
                side_effect=httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=MagicMock()),
            ),
            pytest.raises(BatchResultDownloadError) as exc_info,
        ):
            model._download_results(mock_client, "http://invalid-url", [])

        assert "Failed to download batch results" in str(exc_info.value)
        assert exc_info.value.url == "http://invalid-url"

    @pytest.mark.asyncio
    async def test_request_raises_invalid_response_error_on_empty_response(self, model: GoogleBatchModel):
        """
        GIVEN a successful batch run that returns no response content
        WHEN request is called
        THEN it should raise an InvalidLLMResponseError
        """
        mock_result = MagicMock()
        mock_result.error = None
        mock_result.response = None
        with (
            patch.object(model, "run_batch", return_value=[mock_result]),
            pytest.raises(InvalidLLMResponseError) as exc_info,
        ):
            await model.request([], None, None)

        assert "No response returned for model" in str(exc_info.value)
