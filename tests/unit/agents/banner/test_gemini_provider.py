from types import SimpleNamespace

from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest


class _FakeModelAPI:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.last_config = None

    def generate_content_stream(self, model, contents, config):
        self.calls.append((model, contents, config))
        self.last_config = config
        yield from self.responses


class _FakeClient:
    def __init__(self, responses):
        self.models = _FakeModelAPI(responses)


def _inline_image(data: bytes, mime_type: str):
    return SimpleNamespace(data=data, mime_type=mime_type)


def _content_with_parts(*parts):
    return SimpleNamespace(parts=list(parts))


def _candidate_with_content(content):
    return SimpleNamespace(content=content)


def test_gemini_provider_returns_image_and_debug_text():
    responses = [
        SimpleNamespace(
            candidates=[
                _candidate_with_content(
                    _content_with_parts(
                        SimpleNamespace(text="first chunk"),
                        SimpleNamespace(inline_data=_inline_image(b"img-bytes", "image/png")),
                    )
                )
            ]
        )
    ]
    client = _FakeClient(responses)
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
    assert result.debug_text == "first chunk"
    call_model, contents, config = client.models.calls[0]
    assert call_model == "models/test"
    assert contents[0].parts[0].text == "banner prompt"
    assert config.response_modalities == ["IMAGE"]
    assert config.image_config.aspect_ratio == "4:3"


def test_gemini_provider_returns_error_when_no_image():
    responses = [
        SimpleNamespace(candidates=[_candidate_with_content(_content_with_parts(SimpleNamespace(text="note")))])
    ]
    client = _FakeClient(responses)
    provider = GeminiImageGenerationProvider(client=client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(
            prompt="prompt", response_modalities=["IMAGE", "TEXT"], aspect_ratio=None
        )
    )

    assert not result.has_image
    assert result.error == "No image data received from API"
    assert result.error_code == "NO_IMAGE_DATA"
    call_model, contents, config = client.models.calls[0]
    assert call_model == "models/test"
    assert contents[0].parts[0].text == "prompt"
    assert config.response_modalities == ["IMAGE", "TEXT"]
    assert config.image_config is None
