import base64
import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.banner.agent import (
    BannerInput,
    ImageGenerationRequest,
    _generate_banner_image,
    generate_banner,
)


@pytest.fixture
def mock_httpx(monkeypatch):
    """Fixture to mock httpx.get for downloading batch results."""
    mock = MagicMock()
    monkeypatch.setattr("httpx.get", mock)
    return mock


class _FakeFiles:
    """Fake genai.Files service."""

    def upload(self, path, display_name, mime_type):
        return SimpleNamespace(name="files/123", uri="gs://files/123")


class _FakeBatches:
    """Fake genai.Batches service."""

    def __init__(self, job_state="SUCCEEDED", job_error=None):
        self.job_state = job_state
        self.job_error = job_error
        self.created_job = None

    def create(self, model, src, config):
        self.created_job = SimpleNamespace(name="jobs/456", output_uri="https://output/results.jsonl")
        return self.created_job

    def get(self, name):
        return SimpleNamespace(
            name=name,
            state=SimpleNamespace(name=self.job_state),
            error=self.job_error,
            output_uri="https://output/results.jsonl",
        )


class _FakeClient:
    """Fake genai.Client."""

    def __init__(self, batch_state="SUCCEEDED", batch_error=None):
        self.files = _FakeFiles()
        self.batches = _FakeBatches(batch_state, batch_error)


@patch("egregora.agents.banner.agent.genai.Client")
@patch("egregora.agents.banner.agent._generate_banner_image", side_effect=ValueError("Unexpected test error"))
def test_generate_banner_propagates_unexpected_error(mock_generate, mock_client, caplog):
    """
    Given an unexpected error occurs inside the banner generation logic
    When the generate_banner function is called
    Then the original exception should be propagated
    And the generic "unexpected error" message should NOT be logged.
    """
    mock_client.return_value = _FakeClient()
    with pytest.raises(ValueError, match="Unexpected test error"):
        with caplog.at_level(logging.ERROR):
            generate_banner("A Title", "A summary")
    assert "An unexpected error occurred during banner generation" not in caplog.text


def test_generate_banner_image_returns_image_and_debug_text(mock_httpx):
    img_data = base64.b64encode(b"img-bytes").decode("utf-8")
    response_json = {
        "response": {
            "candidates": [
                {"content": {"parts": [{"text": "debug info"}, {"inlineData": {"mimeType": "image/png", "data": img_data}}]}}
            ]
        }
    }
    mock_httpx.return_value.text = json.dumps(response_json)
    mock_httpx.return_value.raise_for_status = MagicMock()

    client = _FakeClient()
    input_data = BannerInput(post_title="A Title", post_summary="A summary", slug="a-title")
    request = ImageGenerationRequest(prompt="A prompt", response_modalities=["IMAGE"], aspect_ratio="4:3")

    result = _generate_banner_image(
        client=client,
        input_data=input_data,
        image_model="models/test",
        generation_request=request,
    )

    assert result.document.content == b"img-bytes"
    assert result.document.metadata["mime_type"] == "image/png"
    assert result.debug_text == "debug info"
    assert result.success is True
    assert client.batches.created_job.name == "jobs/456"


def test_generate_banner_image_returns_error_when_no_image(mock_httpx):
    response_json = {"response": {"candidates": [{"content": {"parts": [{"text": "just text"}]}}]}}
    mock_httpx.return_value.text = json.dumps(response_json)
    mock_httpx.return_value.raise_for_status = MagicMock()

    client = _FakeClient()
    input_data = BannerInput(post_title="A Title", post_summary="A summary", slug="a-title")
    request = ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio=None)

    result = _generate_banner_image(
        client=client,
        input_data=input_data,
        image_model="models/test",
        generation_request=request,
    )

    assert result.document is None
    assert result.error == "No image data found in response"
    assert result.error_code == "NO_IMAGE"
    assert result.success is False


def test_generate_banner_image_handles_batch_failure():
    client = _FakeClient(batch_state="FAILED", batch_error="Something went wrong")
    input_data = BannerInput(post_title="A Title", post_summary="A summary", slug="a-title")
    request = ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio=None)

    with patch("time.sleep", return_value=None):
        result = _generate_banner_image(
            client=client,
            input_data=input_data,
            image_model="models/test",
            generation_request=request,
        )

    assert result.document is None
    assert result.error == "Batch job failed with state FAILED: Something went wrong"
    assert result.error_code == "BATCH_FAILED"
    assert result.success is False
