import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest


@pytest.fixture
def mock_httpx(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("httpx.get", mock)
    return mock


class _FakeFiles:
    def upload(self, file, config):
        return SimpleNamespace(name="files/123", uri="gs://files/123")


class _FakeBatches:
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
    def __init__(self, batch_state="SUCCEEDED", batch_error=None):
        self.files = _FakeFiles()
        self.batches = _FakeBatches(batch_state, batch_error)


def test_gemini_provider_returns_image_and_debug_text(mock_httpx):
    # Mock successful batch response
    img_data = base64.b64encode(b"img-bytes").decode("utf-8")
    response_json = {
        "response": {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "debug info"},
                            {"inlineData": {"mimeType": "image/png", "data": img_data}},
                        ]
                    }
                }
            ]
        }
    }
    mock_httpx.return_value.text = json.dumps(response_json)
    mock_httpx.return_value.raise_for_status = MagicMock()

    client = _FakeClient()
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(
            prompt="banner prompt",
            response_modalities=["IMAGE"],
            aspect_ratio="4:3",
        )
    )

    assert result.image_bytes == b"img-bytes"
    assert result.mime_type == "image/png"
    assert result.debug_text == "debug info"

    # Verify upload called
    assert client.batches.created_job.name == "jobs/456"


def test_gemini_provider_returns_error_when_no_image(mock_httpx):
    # Mock response without image
    response_json = {
        "response": {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "just text"},
                        ]
                    }
                }
            ]
        }
    }
    mock_httpx.return_value.text = json.dumps(response_json)
    mock_httpx.return_value.raise_for_status = MagicMock()

    client = _FakeClient()
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio=None)
    )

    assert not result.has_image
    assert result.error == "No image data found in response"
    assert result.error_code == "NO_IMAGE"


def test_gemini_provider_handles_batch_failure():
    client = _FakeClient(batch_state="FAILED", batch_error="Something went wrong")
    provider = GeminiImageGenerationProvider(client=client, model="models/test")
    provider._poll_interval = 0  # Speed up test

    result = provider.generate(
        ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"])
    )

    assert not result.has_image
    assert result.error == "Batch job failed with state FAILED: Something went wrong"
    assert result.error_code == "BATCH_FAILED"
