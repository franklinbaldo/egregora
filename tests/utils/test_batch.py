"""Unit tests for batch processing utilities."""

from __future__ import annotations

from unittest import mock

import pytest
from google.api_core import exceptions as google_exceptions
from google.genai import types as genai_types

from egregora.utils.batch import (
    BatchPromptRequest,
    EmbeddingBatchRequest,
    GeminiBatchClient,
    call_with_retries_sync,
)


@pytest.fixture
def mock_genai_client():
    """Fixture for a mocked GenAI client."""
    return mock.MagicMock()


def test_gemini_batch_client_init(mock_genai_client):
    """Test GeminiBatchClient initialization."""
    client = GeminiBatchClient(mock_genai_client, "gemini-1.5-pro")
    assert client.default_model == "gemini-1.5-pro"


def test_gemini_batch_client_generate_content(mock_genai_client):
    """Test batch content generation."""
    mock_job = mock.MagicMock()
    mock_job.name = "test-job"
    mock_job.done = True
    mock_job.state.name = "JOB_STATE_SUCCEEDED"

    # Create a mock response object that mimics genai_types.GenerateContentResponse
    mock_response = mock.MagicMock()
    mock_part = mock.MagicMock()
    mock_part.text = "response"
    mock_response.parts = [mock_part]

    mock_job.dest.inlined_responses = [mock.MagicMock(response=mock_response, error=None)]
    mock_genai_client.batches.create.return_value = mock_job
    mock_genai_client.batches.get.return_value = mock_job

    client = GeminiBatchClient(mock_genai_client, "gemini-1.5-pro")
    requests = [BatchPromptRequest(contents=[genai_types.Content(parts=[genai_types.Part(text="prompt")])])]
    results = client.generate_content(requests)

    assert len(results) == 1
    assert results[0].response.parts[0].text == "response"
    assert results[0].error is None


def test_gemini_batch_client_embed_content(mock_genai_client):
    """Test batch content embedding."""
    mock_job = mock.MagicMock()
    mock_job.name = "test-job"
    mock_job.done = True
    mock_job.state.name = "JOB_STATE_SUCCEEDED"

    # Create a mock response object that mimics genai_types.EmbedContentResponse
    mock_embedding = mock.MagicMock()
    mock_embedding.values = [0.1, 0.2, 0.3]
    mock_response = mock.MagicMock()
    mock_response.embedding = mock_embedding

    mock_job.dest.inlined_embed_content_responses = [mock.MagicMock(response=mock_response, error=None)]
    mock_genai_client.batches.create_embeddings.return_value = mock_job
    mock_genai_client.batches.get.return_value = mock_job

    client = GeminiBatchClient(mock_genai_client, "embedding-001")
    requests = [EmbeddingBatchRequest(text="text")]
    results = client.embed_content(requests)

    assert len(results) == 1
    assert results[0].embedding == [0.1, 0.2, 0.3]
    assert results[0].error is None


def test_gemini_batch_client_generate_content_failed_job(mock_genai_client):
    """Test batch content generation with a failed job."""
    mock_job = mock.MagicMock()
    mock_job.name = "test-job"
    mock_job.done = True
    mock_job.state.name = "JOB_STATE_FAILED"
    mock_job.error.message = "Job failed"

    mock_genai_client.batches.create.return_value = mock_job
    mock_genai_client.batches.get.return_value = mock_job

    client = GeminiBatchClient(mock_genai_client, "gemini-1.5-pro")
    requests = [BatchPromptRequest(contents=[genai_types.Content(parts=[genai_types.Part(text="prompt")])])]

    with pytest.raises(
        RuntimeError, match="Batch job test-job finished with state JOB_STATE_FAILED: Job failed"
    ):
        client.generate_content(requests)


def test_gemini_batch_client_poll_timeout(mock_genai_client):
    """Test batch polling timeout."""
    mock_job = mock.MagicMock()
    mock_job.name = "test-job"
    mock_job.done = False

    mock_genai_client.batches.create.return_value = mock_job
    mock_genai_client.batches.get.return_value = mock_job

    client = GeminiBatchClient(mock_genai_client, "gemini-1.5-pro", poll_interval=0.1)
    requests = [BatchPromptRequest(contents=[genai_types.Content(parts=[genai_types.Part(text="prompt")])])]

    with pytest.raises(TimeoutError, match="Batch job test-job exceeded timeout"):
        client.generate_content(requests, timeout=0.2)


@mock.patch("time.sleep", return_value=None)
def test_call_with_retries_sync(_mock_sleep):
    """Test retry logic."""
    func = mock.MagicMock()
    func.side_effect = [
        google_exceptions.ServiceUnavailable("Service Unavailable"),
        "Success",
    ]
    result = call_with_retries_sync(func)
    assert result == "Success"
    assert func.call_count == 2
