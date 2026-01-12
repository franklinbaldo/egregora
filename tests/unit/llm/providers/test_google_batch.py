"""Unit tests for the GoogleBatchModel LLM provider."""

from unittest.mock import MagicMock, PropertyMock, patch

import httpx
import pytest
from google import genai as genai_client
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

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

    @pytest.mark.asyncio
    async def test_request_raises_usage_limit_exceeded_on_quota_error(self, model: GoogleBatchModel):
        """
        GIVEN a batch run that returns a quota error
        WHEN request is called
        THEN it should raise a UsageLimitExceeded error
        """
        mock_result = MagicMock()
        mock_result.error = {"code": 429, "message": "Quota exceeded for model"}
        mock_result.response = None
        with (
            patch.object(model, "run_batch", return_value=[mock_result]),
            pytest.raises(UsageLimitExceeded) as exc_info,
        ):
            await model.request([], None, None)

        assert "Quota exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_raises_model_http_error_on_generic_error(self, model: GoogleBatchModel):
        """
        GIVEN a batch run that returns a generic error
        WHEN request is called
        THEN it should raise a ModelHTTPError
        """
        mock_result = MagicMock()
        mock_result.error = {"code": 500, "message": "Internal Server Error"}
        mock_result.response = None
        with (
            patch.object(model, "run_batch", return_value=[mock_result]),
            pytest.raises(ModelHTTPError) as exc_info,
        ):
            await model.request([], None, None)

        assert "Internal Server Error" in str(exc_info.value)
        assert exc_info.value.status_code == 500

    def test_run_batch_raises_usage_limit_exceeded_on_quota_error(self, model: GoogleBatchModel):
        """
        GIVEN a ClientError with a 429 status code
        WHEN run_batch is called
        THEN it should raise a UsageLimitExceeded error
        """
        with patch("google.genai.errors.ClientError.__init__", return_value=None):
            error = genai_client.errors.ClientError()
            error.code = 429
            error.message = "Quota exceeded"

            mock_client_instance = MagicMock()
            mock_client_instance.batches.create.side_effect = error
            with (
                patch.object(genai_client, "Client", return_value=mock_client_instance),
                pytest.raises(UsageLimitExceeded) as exc_info,
            ):
                model.run_batch([{"tag": "req-0", "contents": [], "config": {}}])

            assert "Quota Exceeded" in str(exc_info.value)

    def test_run_batch_raises_model_http_error_on_generic_error(self, model: GoogleBatchModel):
        """
        GIVEN a generic ClientError
        WHEN run_batch is called
        THEN it should raise a ModelHTTPError
        """
        with patch("google.genai.errors.ClientError.__init__", return_value=None):
            error = genai_client.errors.ClientError("Internal Server Error")
            error.code = 500

            mock_client_instance = MagicMock()
            mock_client_instance.batches.create.side_effect = error
            with (
                patch.object(genai_client, "Client", return_value=mock_client_instance),
                pytest.raises(ModelHTTPError) as exc_info,
            ):
                model.run_batch([{"tag": "req-0", "contents": [], "config": {}}])

            assert "Internal Server Error" in str(exc_info.value)
            assert exc_info.value.status_code == 500

    def test_response_to_dict_conversion_happy_path(self, model: GoogleBatchModel):
        """
        GIVEN a standard mock SDK response object
        WHEN _response_to_dict is called
        THEN it should correctly convert the object to a dictionary.
        """
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()

        mock_part.text = "This is a test."
        mock_content.parts = [mock_part]
        mock_content.role = "model"
        mock_candidate.content = mock_content
        mock_response.candidates = [mock_candidate]

        expected_dict = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "This is a test."}],
                        "role": "model",
                    }
                }
            ]
        }
        result_dict = model._response_to_dict(mock_response)
        assert result_dict == expected_dict

    def test_response_to_dict_empty_candidates(self, model: GoogleBatchModel):
        """
        GIVEN a mock response with an empty candidates list
        WHEN _response_to_dict is called
        THEN it should return a dictionary with an empty candidates list.
        """
        mock_response = MagicMock()
        mock_response.candidates = []
        expected_dict = {"candidates": []}
        result_dict = model._response_to_dict(mock_response)
        assert result_dict == expected_dict

    def test_response_to_dict_no_content(self, model: GoogleBatchModel):
        """
        GIVEN a mock candidate with no content attribute
        WHEN _response_to_dict is called
        THEN it should produce a candidate with an empty content dict.
        """
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        type(mock_candidate).content = PropertyMock(return_value=None)
        mock_response.candidates = [mock_candidate]
        expected_dict = {"candidates": [{"content": {}}]}
        result_dict = model._response_to_dict(mock_response)
        assert result_dict == expected_dict

    def test_response_to_dict_no_parts(self, model: GoogleBatchModel):
        """
        GIVEN mock content with no parts attribute
        WHEN _response_to_dict is called
        THEN it should produce content with an empty parts list.
        """
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        type(mock_content).parts = PropertyMock(return_value=None)
        mock_content.role = "model"
        mock_candidate.content = mock_content
        mock_response.candidates = [mock_candidate]
        expected_dict = {"candidates": [{"content": {"parts": [], "role": "model"}}]}
        result_dict = model._response_to_dict(mock_response)
        assert result_dict == expected_dict

    def test_response_to_dict_part_no_text(self, model: GoogleBatchModel):
        """
        GIVEN a mock part with no text attribute
        WHEN _response_to_dict is called
        THEN it should be excluded from the parts list.
        """
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        # This is tricky with MagicMock. We have to delete the attribute
        # after it's been accessed and created. A better way is to use
        # a spec or a real object, but for this we'll force it.
        del mock_part.text

        mock_content.parts = [mock_part]
        mock_content.role = "model"
        mock_candidate.content = mock_content
        mock_response.candidates = [mock_candidate]
        expected_dict = {"candidates": [{"content": {"parts": [], "role": "model"}}]}
        result_dict = model._response_to_dict(mock_response)
        assert result_dict == expected_dict

    def test_response_to_dict_complex_structure(self, model: GoogleBatchModel):
        """
        GIVEN a complex response with multiple candidates and parts
        WHEN _response_to_dict is called
        THEN it should correctly parse the entire structure.
        """
        mock_response = MagicMock()

        # Candidate 1: two parts, one valid, one not
        mock_cand1 = MagicMock()
        mock_cont1 = MagicMock()
        mock_part1a = MagicMock()
        mock_part1a.text = "First part."
        mock_part1b = MagicMock()
        del mock_part1b.text  # No text here
        mock_cont1.parts = [mock_part1a, mock_part1b]
        mock_cont1.role = "model"
        mock_cand1.content = mock_cont1

        # Candidate 2: no content
        mock_cand2 = MagicMock()
        type(mock_cand2).content = PropertyMock(return_value=None)

        # Candidate 3: content, but no parts
        mock_cand3 = MagicMock()
        mock_cont3 = MagicMock()
        type(mock_cont3).parts = PropertyMock(return_value=None)
        mock_cont3.role = "model"
        mock_cand3.content = mock_cont3

        mock_response.candidates = [mock_cand1, mock_cand2, mock_cand3]

        expected_dict = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "First part."}],
                        "role": "model",
                    }
                },
                {"content": {}},
                {"content": {"parts": [], "role": "model"}},
            ]
        }
        result_dict = model._response_to_dict(mock_response)
        assert result_dict == expected_dict
