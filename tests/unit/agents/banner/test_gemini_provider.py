from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest


class _FakeClient:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception

    def generate_content(self, prompt):
        if self._exception:
            raise self._exception
        return self._response


def test_gemini_provider_returns_image_and_debug_text():
    # Mock successful response
    img_data = b"img-bytes"
    mime_type = "image/png"

    # Structure matching response.parts[0].inline_data.data
    mock_response = SimpleNamespace(
        parts=[
            SimpleNamespace(
                inline_data=SimpleNamespace(
                    data=img_data,
                    mime_type=mime_type
                )
            )
        ]
    )

    client = _FakeClient(response=mock_response)
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


def test_gemini_provider_handles_exception():
    client = _FakeClient(exception=Exception("API Error"))
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"])
    )

    assert not result.has_image
    assert result.error == "API Error"
    assert result.error_code == "GENERATION_FAILED"
