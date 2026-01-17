from types import SimpleNamespace

from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest


class _FakePart:
    def __init__(self, text=None, inline_data=None):
        self.text = text
        self.inline_data = inline_data


class _FakeResponse:
    def __init__(self, parts):
        self.parts = parts


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def generate_content(self, prompt):
        if self.error:
            raise self.error
        return self.response


def test_gemini_provider_returns_image():
    # Mock successful response
    img_data = b"img-bytes"
    mime_type = "image/png"

    inline_data = SimpleNamespace(data=img_data, mime_type=mime_type)
    parts = [_FakePart(inline_data=inline_data)]
    response = _FakeResponse(parts=parts)

    client = _FakeClient(response=response)
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
    assert result.error is None


def test_gemini_provider_returns_error_when_exception_occurs():
    # Mock exception
    client = _FakeClient(error=Exception("API Error"))
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio=None)
    )

    assert not result.has_image
    assert result.error == "API Error"
    assert result.error_code == "GENERATION_FAILED"


def test_gemini_provider_returns_error_when_response_structure_invalid():
    # Mock response without parts (should raise IndexError or AttributeError in implementation)
    response = _FakeResponse(parts=[])
    client = _FakeClient(response=response)
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio=None)
    )

    assert not result.has_image
    assert "list index out of range" in result.error
    assert result.error_code == "GENERATION_FAILED"


def test_generate_content_returns_empty_parts():
    """Test behavior when API returns no content (e.g. safety block)."""
    # Arrange
    response = _FakeResponse(parts=[])
    client = _FakeClient(response=response)
    provider = GeminiImageGenerationProvider(client=client, model="models/test")
    request = ImageGenerationRequest(prompt="unsafe prompt", response_modalities=["IMAGE"])

    # Act
    result = provider.generate(request)

    # Assert
    assert not result.has_image
    assert result.error_code == "GENERATION_FAILED"
    # The actual error string depends on implementation (likely IndexError or generic)
    # The current implementation catches generic Exception and logs it.
    assert result.error is not None


def test_generate_content_returns_parts_without_inline_data():
    """Test behavior when API returns parts but no inline data."""
    # Arrange
    # Part without inline_data
    parts = [_FakePart(inline_data=None)]
    response = _FakeResponse(parts=parts)
    client = _FakeClient(response=response)
    provider = GeminiImageGenerationProvider(client=client, model="models/test")
    request = ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"])

    # Act
    result = provider.generate(request)

    # Assert
    assert not result.has_image
    assert result.error_code == "GENERATION_FAILED"
    assert result.error is not None


def test_generate_content_raises_api_error():
    """Test behavior when API raises an error."""
    # Arrange
    error_msg = "Rate limit exceeded"
    client = _FakeClient(error=Exception(error_msg))
    provider = GeminiImageGenerationProvider(client=client, model="models/test")
    request = ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"])

    # Act
    result = provider.generate(request)

    # Assert
    assert not result.has_image
    assert result.error == error_msg
    assert result.error_code == "GENERATION_FAILED"
