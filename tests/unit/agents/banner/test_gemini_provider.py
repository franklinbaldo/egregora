from unittest.mock import MagicMock

import pytest

from egregora.agents.banner.exceptions import BannerNoImageError
from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest


@pytest.fixture
def _mock_httpx(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("httpx.get", mock)
    return mock


class _FakeInlineData:
    """Mock inline_data from a response part."""

    def __init__(self, data: bytes, mime_type: str = "image/png"):
        self.data = data
        self.mime_type = mime_type


class _FakePart:
    """Mock part of a response."""

    def __init__(self, inline_data: _FakeInlineData | None = None, text: str | None = None):
        self.inline_data = inline_data
        self.text = text


class _FakeContent:
    """Mock content attribute on candidate."""

    def __init__(self, parts: list[_FakePart]):
        self.parts = parts


class _FakeCandidate:
    """Mock candidate in a response."""

    def __init__(self, content: _FakeContent):
        self.content = content


class _FakeResponse:
    """Mock response from generate_content."""

    def __init__(self, parts: list[_FakePart]):
        self.candidates = [_FakeCandidate(content=_FakeContent(parts=parts))]


class _FakeModels:
    """Mock models attribute on client."""

    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None):
        self._response = response
        self._error = error

    def generate_content(self, *args, **kwargs):
        if self._error:
            raise self._error
        return self._response


class _FakeClient:
    """Mock genai.Client that returns generate_content responses."""

    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None):
        self.models = _FakeModels(response=response, error=error)


def test_gemini_provider_returns_image_and_debug_text(_mock_httpx):
    # Mock successful response with image data
    img_bytes = b"img-bytes"
    response = _FakeResponse(
        parts=[
            _FakePart(inline_data=_FakeInlineData(data=img_bytes, mime_type="image/png")),
        ]
    )

    client = _FakeClient(response=response)
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(
            prompt="banner prompt",
            response_modalities=["IMAGE"],
            aspect_ratio="4:3",
        )
    )

    assert result.image_bytes == img_bytes
    assert result.mime_type == "image/png"


def test_gemini_provider_raises_error_when_no_image(_mock_httpx):
    # Mock response without inline_data (only text)
    response = _FakeResponse(
        parts=[
            _FakePart(text="just text"),
        ]
    )

    client = _FakeClient(response=response)
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    with pytest.raises(BannerNoImageError, match="No image data found"):
        provider.generate(
            ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio=None)
        )


def test_gemini_provider_handles_batch_failure():
    # Mock an exception from generate_content
    error = Exception("API call failed: Something went wrong")
    client = _FakeClient(error=error)
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    with pytest.raises(Exception, match="API call failed: Something went wrong"):
        provider.generate(ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"]))
