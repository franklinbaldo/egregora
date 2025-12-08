from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from egregora.config.settings import (
    ModelSettings,
    RAGSettings,
    create_default_config,
)
from egregora.input_adapters.whatsapp import WhatsAppExport, discover_chat_file
from egregora.utils.zip import validate_zip_contents
from tests.utils.mock_batch_client import MockGeminiClient

try:
    import ibis
except ImportError:  # pragma: no cover - depends on test env
    pytest.skip(
        "ibis is required for the test suite; install project dependencies to run tests",
        allow_module_level=True,
    )


@pytest.fixture(autouse=True)
def _ibis_backend(request):
    # CLI init tests don't exercise Ibis; avoid importing backends there to prevent
    # unrelated failures when Ibis dependency chains break.
    if "tests/e2e/cli" in str(getattr(request.node, "fspath", "")):
        yield
        return

    # In ibis 9.0+, use connect() with database path directly
    # We let this raise if backend fails, so we can understand the error
    backend = ibis.duckdb.connect(":memory:")

    options = getattr(ibis, "options", None)
    previous_backend = getattr(options, "default_backend", None) if options else None

    try:
        if options is not None:
            options.default_backend = backend
        yield
    finally:
        if options is not None:
            options.default_backend = previous_backend
        # Close backend to release resources
        if hasattr(backend, "disconnect"):
            backend.disconnect()


@dataclass(slots=True)
class WhatsAppFixture:
    """Metadata helper so tests can easily construct ``WhatsAppExport`` objects."""

    zip_path: Path
    group_name: str
    group_slug: str
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
    group_slug = group_name.lower().replace(" ", "-")
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
        "egregora.agents.enricher.create_url_enrichment_agent",
        lambda model, _simple=True: _stub_url_agent(model),
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.agents.enricher.create_media_enrichment_agent",
        lambda model: _stub_media_agent(model),
        raising=False,
    )
    monkeypatch.setattr("egregora.agents.enricher._run_url_enrichment_async", _stub_url_run, raising=False)
    monkeypatch.setattr(
        "egregora.agents.enricher._run_media_enrichment_async", _stub_media_run, raising=False
    )


@pytest.fixture
def mock_batch_client(monkeypatch):
    """Mock batch client for embedding requests."""
    client = MockGeminiClient()
    monkeypatch.setattr("egregora.utils.batch.GeminiBatchClient", lambda **k: client)
    return client


@pytest.fixture
def default_config():
    return create_default_config(site_root=Path.cwd())


@pytest.fixture
def rag_config(default_config):
    default_config.rag = RAGSettings(enabled=True, index_path=":memory:")
    default_config.models = ModelSettings(embedding="test-embedding-model", writer="test-writer-model")
    return default_config


@pytest.fixture
def minimal_config():
    """Provide a minimal configuration object with default settings."""

    return create_default_config(site_root=Path.cwd())


@pytest.fixture
def config_factory():
    """Create configuration objects with convenient overrides."""

    def _factory(**overrides):
        config = create_default_config(site_root=Path.cwd())
        for path, value in overrides.items():
            target = config
            parts = path.split("__")
            for part in parts[:-1]:
                target = getattr(target, part)
            setattr(target, parts[-1], value)
        return config

    return _factory


@pytest.fixture
def writer_test_agent():
    """Skip writer e2e tests when deterministic test agent is unavailable."""

    pytest.skip("writer_test_agent fixture is not available in this environment")


@pytest.fixture
def reader_test_config():
    """Skip reader e2e tests when dedicated config is unavailable."""

    pytest.skip("reader_test_config fixture is not available in this environment")


@pytest.fixture(autouse=True)
def mock_embedding_model(monkeypatch):
    """Mock embedding model to avoid API calls."""
    monkeypatch.setattr(
        "egregora.rag.embedding_router.create_embedding_router",
        lambda *a, **k: SimpleNamespace(
            embed_documents=lambda texts, **kw: [[0.1] * 768 for _ in texts],
            embed_query=lambda text, **kw: [0.1] * 768,
            stop=lambda: None,
        ),
    )
