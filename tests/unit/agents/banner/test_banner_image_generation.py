import pytest

from egregora.agents.banner import agent
from egregora.agents.banner.agent import BannerInput, _generate_banner_image
from egregora.agents.banner.image_generation import ImageGenerationRequest, ImageGenerationResult
from egregora.data_primitives.document import DocumentType


class _FakeProvider:
    def __init__(self, *, result: ImageGenerationResult):
        self.result = result
        self.seen_request: ImageGenerationRequest | None = None
        self.init_kwargs: dict[str, object] | None = None

    def __call__(self, client, model):
        self.init_kwargs = {"client": client, "model": model}
        return self

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self.seen_request = request
        return self.result


@pytest.fixture()
def fake_provider(monkeypatch):
    provider = _FakeProvider(
        result=ImageGenerationResult(
            image_bytes=b"banner-bytes",
            mime_type="image/png",
            debug_text="debug info",
        )
    )
    monkeypatch.setattr(agent, "GeminiImageGenerationProvider", provider)
    return provider


def test_generate_banner_image_preserves_request_prompt(fake_provider):
    request = ImageGenerationRequest(
        prompt="custom prompt",
        response_modalities=["IMAGE"],
        aspect_ratio="1:1",
    )
    input_data = BannerInput(
        post_title="Title",
        post_summary="Summary",
        slug="sluggy",
        language="en",
    )

    output = _generate_banner_image(
        client=object(),
        input_data=input_data,
        image_model="model-id",
        generation_request=request,
    )

    assert request.prompt == "custom prompt"
    assert fake_provider.seen_request is request
    assert fake_provider.seen_request.prompt == "custom prompt"
    assert output.success
    assert output.document is not None
    assert output.document.metadata["slug"] == "sluggy"
    assert output.document.metadata["language"] == "en"
    assert output.document.type is DocumentType.MEDIA
    assert output.debug_text == "debug info"
