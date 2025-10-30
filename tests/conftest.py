from __future__ import annotations

import sys
import types
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import duckdb
import pytest

try:
    import ibis  # noqa: F401 - imported to ensure availability for fixtures
except ImportError:  # pragma: no cover - depends on test env
    pytest.skip(
        "ibis is required for the test suite; install project dependencies to run tests",
        allow_module_level=True,
    )


def _install_google_stubs() -> None:
    """Ensure google genai modules exist so imports succeed during tests."""

    if "google" in sys.modules:
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
                upload=lambda *a, **k: types.SimpleNamespace(uri="stub://file", mime_type="application/octet-stream")
            )

            dummy_job = types.SimpleNamespace(
                name="stub-job",
                dest=types.SimpleNamespace(inlined_responses=[]),
                state=types.SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
                done=True,
                error=None,
            )
            self.batches = types.SimpleNamespace(create=lambda *a, **k: dummy_job, get=lambda *a, **k: dummy_job)

        def close(self) -> None:  # pragma: no cover - compatibility stub
            return None

    # Populate genai.types namespace with simple containers used in code paths.
    for attr in (
        "Schema",
        "FunctionDeclaration",
        "Tool",
        "FunctionResponse",
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


from egregora.core.models import WhatsAppExport
from egregora.core.types import GroupSlug
from egregora.orchestration.pipeline import discover_chat_file
from egregora.utils.zip import validate_zip_contents


@pytest.fixture(autouse=True)
def ibis_backend():
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

    zip_path = Path(__file__).parent / "Conversa do WhatsApp com Teste.zip"
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


@pytest.fixture()
def gemini_api_key() -> str:
    return "test-key"


@pytest.fixture()
def mock_batch_client(monkeypatch):
    """Monkey-patch GeminiBatchClient and genai.Client with mocks for fast tests.

    This fixture replaces all API client instances with mocks that return
    instant fake responses without API calls. Tests run ~100x faster.

    Usage:
        def test_with_mock(mock_batch_client):
            # All API calls are now mocked
            process_whatsapp_export(...)
    """
    from tests.mock_batch_client import MockGeminiBatchClient, MockGeminiClient

    # Patch genai.Client - this is the main client used everywhere
    monkeypatch.setattr(
        "google.genai.Client",
        MockGeminiClient,
    )
    # Patch where genai is imported in egregora modules
    monkeypatch.setattr(
        "egregora.orchestration.pipeline.genai.Client",
        MockGeminiClient,
    )
    monkeypatch.setattr(
        "egregora.generation.editor.agent.genai.Client",
        MockGeminiClient,
    )

    # Patch the GeminiBatchClient class at import locations
    monkeypatch.setattr(
        "egregora.utils.batch.GeminiBatchClient",
        MockGeminiBatchClient,
    )
    monkeypatch.setattr(
        "egregora.orchestration.pipeline.GeminiBatchClient",
        MockGeminiBatchClient,
    )
    monkeypatch.setattr(
        "egregora.generation.editor.agent.GeminiBatchClient",
        MockGeminiBatchClient,
    )

    yield {
        "client": MockGeminiClient,
        "batch_client": MockGeminiBatchClient,
    }


@pytest.fixture
def playback_client():
    """Gemini client that replays golden fixtures."""
    from egregora.testing.gemini_playback import GeminiClientPlayback

    fixtures_dir = Path(__file__).parent / "fixtures/golden/api_responses"
    return GeminiClientPlayback(fixtures_dir)
