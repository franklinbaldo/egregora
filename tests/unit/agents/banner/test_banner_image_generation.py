import importlib.util
import sys
import types

import pytest

google_api_core_spec = importlib.util.find_spec("google.api_core")
if google_api_core_spec is not None:
    from google.api_core import exceptions as google_exceptions
else:  # pragma: no cover - exercised when Google SDKs are absent
    GoogleAPICallError = type("GoogleAPICallError", (Exception,), {})
    google_exceptions = types.SimpleNamespace(
        GoogleAPICallError=GoogleAPICallError,
        ResourceExhausted=type("ResourceExhausted", (GoogleAPICallError,), {}),
    )
    google_api_core = types.ModuleType("google.api_core")
    google_api_core.exceptions = google_exceptions
    sys.modules.setdefault("google.api_core", google_api_core)

from google.genai import errors as google_exceptions  # noqa: E402

from egregora.agents.banner import agent  # noqa: E402
from egregora.agents.banner.agent import BannerInput, _generate_banner_image  # noqa: E402
from egregora.agents.banner.exceptions import BannerGenerationError  # noqa: E402
from egregora.agents.banner.image_generation import (  # noqa: E402
    ImageGenerationRequest,
    ImageGenerationResult,
)
from egregora.data_primitives.document import DocumentType  # noqa: E402


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


@pytest.fixture
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
    assert output.document is not None
    assert output.document.metadata["slug"] == "sluggy"
    assert output.document.metadata["language"] == "en"
    assert output.document.type is DocumentType.MEDIA
    assert output.debug_text == "debug info"


def test_generate_banner_image_handles_api_error(monkeypatch):
    """Test that API errors from the provider are propagated for retry handling."""
    # 1. Arrange
    from google.genai import errors as google_exceptions

    class FailingProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
            msg = "Rate limit exceeded"
            raise google_exceptions.APIError(msg, response_json={})

    monkeypatch.setattr(agent, "GeminiImageGenerationProvider", FailingProvider)

    request = ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio="1:1")
    input_data = BannerInput(post_title="Title", post_summary="Summary")

    # 2. Act & Assert
    with pytest.raises(google_exceptions.APIError, match="Rate limit exceeded"):
        _generate_banner_image(
            client=object(),
            input_data=input_data,
            image_model="model-id",
            generation_request=request,
        )


def test_generate_banner_reraises_unexpected_errors(monkeypatch):
    """Test that the main `generate_banner` function reraises unexpected errors."""

    # 1. Arrange
    def mock_generate_banner_image(*args, **kwargs):
        msg = "Something went wrong"
        raise ValueError(msg)

    monkeypatch.setenv("EGREGORA_SKIP_API_KEY_VALIDATION", "1")
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-key")
    monkeypatch.setattr(agent, "_generate_banner_image", mock_generate_banner_image)
    # Mock the genai.Client at the module level where it's imported

    # Patch the Client where it is used in the agent module
    monkeypatch.setattr(agent.genai, "Client", lambda *a, **kw: object())

    # Mocking EgregoraConfig to return an object with a .models.banner attribute
    class MockModels:
        banner = "test-model"

    class MockConfig:
        models = MockModels()
        image_generation = type(
            "ImageGenerationSettings", (), {"response_modalities": ["IMAGE"], "aspect_ratio": "1:1"}
        )()

    monkeypatch.setattr(agent, "EgregoraConfig", MockConfig)

    # 2. Act & Assert
    with pytest.raises(ValueError, match="Something went wrong"):
        agent.generate_banner(post_title="Title", post_summary="Summary")


def test_generate_banner_image_reraises_unexpected_errors(monkeypatch):
    """Test that unexpected (non-API) errors are not caught."""

    # 1. Arrange
    class FailingProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
            # This simulates a bug inside the provider, not a remote API error
            msg = "A bug in the provider"
            raise TypeError(msg)

    monkeypatch.setattr(agent, "GeminiImageGenerationProvider", FailingProvider)

    request = ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio="1:1")
    input_data = BannerInput(post_title="Title", post_summary="Summary")

    # 2. Act & Assert
    with pytest.raises(TypeError, match="A bug in the provider"):
        _generate_banner_image(
            client=object(),
            input_data=input_data,
            image_model="model-id",
            generation_request=request,
        )
