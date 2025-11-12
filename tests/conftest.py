from __future__ import annotations

import base64
import sys
import types
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STUBS_PATH = Path(__file__).resolve().parent / "_stubs"
SRC_PATH = PROJECT_ROOT / "src"

if str(STUBS_PATH) not in sys.path:
    sys.path.insert(0, str(STUBS_PATH))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

try:
    import ibis
except ImportError:  # pragma: no cover - depends on test env
    pytest.skip(
        "ibis is required for the test suite; install project dependencies to run tests",
        allow_module_level=True,
    )


try:  # Prefer the real SDK if it is available in the environment.
    from google.genai import types as genai_types  # type: ignore[import-not-found]

    # Some historical versions lacked the newer helper classes we rely on.
    _real_sdk_available = bool(hasattr(genai_types, "FunctionCall"))
except (ImportError, AttributeError):  # pragma: no cover - runtime safety for optional dependency
    # SDK not installed or incompatible version
    _real_sdk_available = False


def _install_google_stubs() -> None:
    """Ensure google genai modules exist so imports succeed during tests."""
    if _real_sdk_available:
        # Some historical versions lacked the newer helper classes we rely on.
        if hasattr(genai_types, "FunctionCall"):
            return

    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_types_module = types.ModuleType("google.genai.types")

    class _SimpleStruct:
        def __init__(self, *args, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _DummyType:
        OBJECT = "object"
        STRING = "string"
        ARRAY = "array"
        INTEGER = "integer"

    class _DummyClient:
        def __init__(self, *args, **kwargs):
            empty_response = types.SimpleNamespace(candidates=[])
            self.models = types.SimpleNamespace(generate_content=lambda *a, **k: empty_response)
            self.aio = types.SimpleNamespace(models=self.models)
            self.files = types.SimpleNamespace(
                upload=lambda *a, **k: types.SimpleNamespace(
                    uri="stub://file", mime_type="application/octet-stream"
                )
            )

            dummy_job = types.SimpleNamespace(
                name="stub-job",
                dest=types.SimpleNamespace(inlined_responses=[]),
                state=types.SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
                done=True,
                error=None,
            )
            self.batches = types.SimpleNamespace(
                create=lambda *a, **k: dummy_job, get=lambda *a, **k: dummy_job
            )

        def close(self) -> None:  # pragma: no cover - compatibility stub
            return None

    # Populate genai.types namespace with simple containers used in code paths.
    for attr in (
        "Schema",
        "FunctionDeclaration",
        "FunctionCall",
        "Tool",
        "FunctionResponse",
        "FunctionCall",
        "Part",
        "Content",
        "GenerateContentConfig",
        "BatchJobSource",
        "CreateBatchJobConfig",
        "InlinedRequest",
        "EmbeddingsBatchJobSource",
        "EmbedContentBatch",
        "EmbedContentConfig",
        "FileData",
        "BatchJob",
        "JobError",
    ):
        setattr(genai_types_module, attr, _SimpleStruct)

    genai_types_module.Type = _DummyType

    google_module.genai = genai_module
    genai_module.types = genai_types_module
    genai_module.Client = _DummyClient

    sys.modules["google"] = google_module
    sys.modules["google.genai"] = genai_module
    sys.modules["google.genai.types"] = genai_types_module


_install_google_stubs()

# Imports below require sys.path setup above
from egregora.sources.whatsapp import WhatsAppExport, discover_chat_file
from egregora.data_primitives import GroupSlug
from egregora.utils.zip import validate_zip_contents
from tests.utils.mock_batch_client import MockGeminiClient


@pytest.fixture(autouse=True)
def _ibis_backend():
    connection = duckdb.connect(":memory:")
    backend = ibis.duckdb.from_connection(connection)
    options = getattr(ibis, "options", None)
    previous_backend = getattr(options, "default_backend", None) if options else None

    try:
        if options is not None:
            options.default_backend = backend
        yield
    finally:
        if options is not None:
            options.default_backend = previous_backend
        connection.close()


@dataclass(slots=True)
class WhatsAppFixture:
    """Metadata helper so tests can easily construct ``WhatsAppExport`` objects."""

    zip_path: Path
    group_name: str
    group_slug: GroupSlug
    chat_file: str
    export_date: date

    def create_export(self) -> WhatsAppExport:
        return WhatsAppExport(
            zip_path=self.zip_path,
            group_name=self.group_name,
            group_slug=self.group_slug,
            export_date=self.export_date,
            chat_file=self.chat_file,
            media_files=[],
        )

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo("America/Sao_Paulo")


@pytest.fixture(scope="session")
def whatsapp_fixture() -> WhatsAppFixture:
    """Load WhatsApp archive metadata once for the entire test session."""
    zip_path = Path(__file__).parent / "fixtures" / "Conversa do WhatsApp com Teste.zip"
    with zipfile.ZipFile(zip_path) as archive:
        validate_zip_contents(archive)
    group_name, chat_file = discover_chat_file(zip_path)
    group_slug = GroupSlug(group_name.lower().replace(" ", "-"))
    return WhatsAppFixture(
        zip_path=zip_path,
        group_name=group_name,
        group_slug=group_slug,
        chat_file=chat_file,
        export_date=date(2025, 10, 28),
    )


@pytest.fixture(scope="session")
def whatsapp_timezone() -> ZoneInfo:
    return ZoneInfo("America/Sao_Paulo")


@pytest.fixture
def gemini_api_key() -> str:
    return "test-key"


@pytest.fixture(autouse=True)
def stub_enrichment_agents(monkeypatch):
    """Provide deterministic enrichment/vision agents for offline tests."""

    def _stub_url_agent(model, prompts_dir=None):
        return object()

    def _stub_media_agent(model, prompts_dir=None):
        return object()

    def _stub_url_run(agent, url, prompts_dir=None):
        return f"Stub enrichment for {url}"

    def _stub_media_run(agent, media_path, **kwargs):
        return f"Stub enrichment for {media_path}"

    monkeypatch.setattr(
        "egregora.enrichment.thin_agents.make_url_agent",
        lambda model, prompts_dir=None: _stub_url_agent(model, prompts_dir),
    )
    monkeypatch.setattr(
        "egregora.enrichment.simple_runner.make_url_agent",
        lambda model, prompts_dir=None: _stub_url_agent(model, prompts_dir),
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.enrichment.thin_agents.make_media_agent",
        lambda model, prompts_dir=None: _stub_media_agent(model, prompts_dir),
    )
    monkeypatch.setattr(
        "egregora.enrichment.simple_runner.make_media_agent",
        lambda model, prompts_dir=None: _stub_media_agent(model, prompts_dir),
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.enrichment.thin_agents.run_url_enrichment",
        lambda agent, url, prompts_dir=None: _stub_url_run(agent, url, prompts_dir),
    )
    monkeypatch.setattr(
        "egregora.enrichment.simple_runner.run_url_enrichment",
        lambda agent, url, prompts_dir=None: _stub_url_run(agent, url, prompts_dir),
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.enrichment.thin_agents.run_media_enrichment",
        lambda agent, file_path, **kwargs: _stub_media_run(agent, file_path, **kwargs),
    )
    monkeypatch.setattr(
        "egregora.enrichment.simple_runner.run_media_enrichment",
        lambda agent, file_path, **kwargs: _stub_media_run(agent, file_path, **kwargs),
        raising=False,
    )

    from types import SimpleNamespace

    def _avatar_agent(_model):
        class _StubAvatar:
            def run_sync(self, *args, **kwargs):
                return SimpleNamespace(
                    output=SimpleNamespace(
                        is_appropriate=True,
                        reason="stub",
                        description="stub",
                    )
                )

        return _StubAvatar()

    monkeypatch.setattr(
        "egregora.enrichment.avatar.create_avatar_enrichment_agent",
        lambda model: _avatar_agent(model),
        raising=False,
    )


@pytest.fixture
def mock_batch_client(monkeypatch):
    """Monkey-patch genai.Client with mocks for fast tests.

    This fixture replaces all API client instances with mocks that return
    instant fake responses without API calls. Tests run ~100x faster.

    Usage:
        def test_with_mock(mock_batch_client):
            # All API calls are now mocked
            process_whatsapp_export(...)
    """
    # Patch genai.Client - this is the main client used everywhere
    monkeypatch.setattr(
        "google.genai.Client",
        MockGeminiClient,
    )
    # Patch where genai is imported in egregora modules
    monkeypatch.setattr(
        "egregora.sources.whatsapp.pipeline.genai.Client",
        MockGeminiClient,
    )

    return MockGeminiClient


def _serialize_request_body(request):
    """Serialize request body, encoding binary data as base64."""
    if hasattr(request, "body") and request.body:
        try:
            # Try to decode as UTF-8 (for JSON/text requests)
            request.body.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            # Binary data - encode as base64 for YAML serialization
            if isinstance(request.body, bytes):
                request.body = base64.b64encode(request.body).decode("ascii")
                request.headers["X-VCR-Binary-Body"] = ["true"]
        else:
            return request
    return request


def _deserialize_request_body(request):
    """Deserialize request body, decoding base64 back to binary if needed."""
    if request.headers.get("X-VCR-Binary-Body") == ["true"]:
        request.body = base64.b64decode(request.body.encode("ascii"))
        del request.headers["X-VCR-Binary-Body"]
    return request


def _serialize_response_body(response):
    """Serialize response body, encoding binary data as base64."""
    if response.get("body"):
        try:
            # Try to decode as UTF-8
            if isinstance(response["body"], bytes):
                response["body"].decode("utf-8")
            elif isinstance(response["body"], str):
                response["body"].encode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            # Binary data - encode as base64
            if isinstance(response["body"], bytes):
                response["body"] = {"string": base64.b64encode(response["body"]).decode("ascii")}
                response["headers"]["X-VCR-Binary-Body"] = ["true"]
        else:
            return response
    return response


@pytest.fixture(scope="module")
def vcr_config():
    """VCR configuration for recording and replaying HTTP interactions.

    This configuration filters out sensitive data like API keys from cassettes
    and properly handles binary file uploads (images, etc.).
    """
    return {
        # Record mode: 'once' means record the first time, then replay
        "record_mode": "once",
        # Directory containing pre-recorded cassettes
        "cassette_library_dir": str(Path(__file__).parent / "cassettes"),
        # Ensure httpx.Client is patched for playback
        "custom_patches": ("httpx",),
        # Filter API keys from recordings
        "filter_headers": [
            ("x-goog-api-key", "DUMMY_API_KEY"),
            ("authorization", "DUMMY_AUTH"),
        ],
        # Filter query parameters with API keys
        "filter_query_parameters": [
            ("key", "DUMMY_API_KEY"),
        ],
        # Match requests on method, scheme, host, port, and path (not body for binary uploads)
        "match_on": ["method", "scheme", "host", "port", "path"],
        # Decode compressed responses
        "decode_compressed_response": True,
        # Handle binary content in requests/responses
        "before_record_request": _serialize_request_body,
        "before_record_response": _serialize_response_body,
    }
