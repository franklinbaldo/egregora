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
from tests.utils.pydantic_test_models import MockEmbeddingModel, install_writer_test_model

try:
    import ibis
    from ibis.common.exceptions import IbisError
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

    try:
        # In ibis 9.0+, use connect() with database path directly
        backend = ibis.duckdb.connect(":memory:")
    except IbisError as exc:  # pragma: no cover - guard against broken ibis deps
        pytest.skip(f"ibis backend unavailable: {exc}")

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
def clean_env(monkeypatch):
    """Ensure environment is clean for tests."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return monkeypatch


@pytest.fixture
def temp_site_dir(tmp_path):
    """Create a temporary directory for site generation."""
    site_dir = tmp_path / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    return site_dir


@pytest.fixture
def mock_vector_store(monkeypatch):
    """Mock the RAG vector store using InMemoryRagBackend."""
    from egregora.rag.backend import InMemoryRagBackend, set_backend

    backend = InMemoryRagBackend()

    # Inject the backend globally
    # This avoids patching individual modules as long as they call egregora.rag.index_documents/search
    # which now delegate to get_backend()
    set_backend(backend)

    # Return the backend so tests can inspect it
    # We return a list-like object for compatibility with existing tests that expect a list
    # of indexed documents, or we can just return the backend.
    # Existing tests checked `mock_vector_store` as a list?
    # Let's check previous code. It returned `{"index": mock_index, "search": mock_search}`.
    # But `test_mock_fixtures_are_available` in pipeline test expected it to be a list?
    # No, it asserted `isinstance(mock_vector_store, list)`.
    # Wait, the previous code for `test_pipeline_with_rag_enabled` comment said:
    # "mock_vector_store is now a list that tracks indexed documents"
    # But the implementation I replaced returned a dict!
    # Ah, I see `tests/e2e/conftest.py` had a `mock_vector_store` fixture too?
    # No, I moved it from there. The version I read earlier:
    # return {"index": mock_index, "search": mock_search}
    # So `test_mock_fixtures_are_available` assertion `isinstance(mock_vector_store, list)`
    # would fail if I kept the dict.
    # But I see in `tests/e2e/pipeline/test_write_pipeline_e2e.py` (which I read earlier):
    # assert isinstance(mock_vector_store, list), "mock_vector_store should be a list tracking indexed docs"
    # So there was a mismatch between fixture implementation and test expectation in the files I read?
    # Or maybe I read a version where it WAS a list?
    # Let's look at `tests/e2e/conftest.py` I read earlier.
    # It had:
    # return {"index": mock_index, "search": mock_search}
    # So the existing test was likely failing or I misread something.
    # Anyway, to be safe and clean, I will make this fixture return the backend object
    # and update the test to check the backend object.

    yield backend

    # Reset to default backend?
    # Since set_backend modifies global state, we should reset it.
    from egregora.rag.backend import DefaultRagBackend
    set_backend(DefaultRagBackend())


@pytest.fixture(autouse=True)
def _disable_network(pytestconfig):
    """Disable network access by default, unless marked with @pytest.mark.network."""
    if pytestconfig.getoption("verbose") > 0:
        print("Disabling network access for tests...")

    # Check if pytest-socket is installed and active
    if pytestconfig.pluginmanager.hasplugin("socket"):
        from pytest_socket import disable_socket, enable_socket

        # Disable all sockets but allow unix sockets for asyncio/DBs
        disable_socket(allow_unix_socket=True)

        yield

        # Re-enable at teardown (though likely unnecessary as fixtures are scoped)
        enable_socket()
    else:
        yield


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
        lambda model, _simple=False: _stub_media_agent(model),
        raising=False,
    )

    async def _stub_url_enrichment_async(agent, url, prompts_dir=None):
        return f"Stub enrichment for {url}"

    async def _stub_media_enrichment_async(agent, file_path, mime_hint=None, prompts_dir=None):
        return f"Stub enrichment for {file_path}"

    monkeypatch.setattr(
        "egregora.agents.enricher._run_url_enrichment_async",
        _stub_url_enrichment_async,
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.agents.enricher._run_media_enrichment_async",
        _stub_media_enrichment_async,
        raising=False,
    )

    def _avatar_agent(_model):
        class _StubAvatar:
            def run_sync(self, *args, **kwargs):
                return SimpleNamespace(
                    output=SimpleNamespace(
                        markdown="Stub enrichment for avatar",
                    )
                )

        return _StubAvatar()

    monkeypatch.setattr(
        "egregora.agents.enricher.create_media_enrichment_agent",
        lambda model, _simple=False: _avatar_agent(model),
        raising=False,
    )




@pytest.fixture
def writer_test_agent(monkeypatch):
    """Install deterministic writer agent built on ``pydantic-ai`` TestModel."""

    captured_windows: list[str] = []
    install_writer_test_model(monkeypatch, captured_windows)
    return captured_windows


@pytest.fixture
def mock_embedding_model():
    """Deterministic embedding stub for tests."""

    return MockEmbeddingModel()


# =============================================================================
# Test Configuration Fixtures - Selection Guide
# =============================================================================
#
# Use these fixtures instead of directly instantiating EgregoraConfig or Settings.
#
# RULE 1: Never use production config in tests
#   ❌ config = EgregoraConfig()  # Uses production defaults!
#   ✅ config = test_config        # Uses test defaults with tmp_path
#
# RULE 2: Pick the right fixture for your test type
#   - Unit tests (fast, no I/O):     minimal_config
#   - Integration tests (with mocks): test_config
#   - E2E tests (full pipeline):     pipeline_test_config
#   - RAG-specific tests:            test_rag_settings_enabled
#   - Reader agent tests:            reader_test_config
#
# RULE 3: Customize with factory or model_copy()
#   - Quick customization:  config_factory(rag__enabled=True)
#   - Full control:         test_config.model_copy(deep=True)
#
# RULE 4: Never hardcode infrastructure
#   ❌ db_path = Path("/var/egregora/db.duckdb")
#   ✅ db_path = tmp_path / "test.duckdb"
#
# =============================================================================


@pytest.fixture
def test_config(tmp_path: Path):
    """Test configuration with tmp_path for isolation.

    Creates a minimal valid configuration using pytest's tmp_path to ensure
    test isolation and prevent tests from affecting each other or the filesystem.

    All tests should use this or derived fixtures instead of manually
    constructing Settings objects.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        EgregoraConfig configured for test environment
    """

    # Create site root in tmp_path for test isolation
    site_root = tmp_path / "site"
    site_root.mkdir(parents=True, exist_ok=True)

    # Create default config with test site_root
    # Create default config with test site_root
    return create_default_config(site_root=site_root)


@pytest.fixture
def reader_test_config(test_config):
    """Configuration with reader agent enabled for testing.

    Use this fixture for tests that involve the reader agent (post evaluation,
    ELO ranking, etc.). Config optimized for fast test execution.

    Args:
        test_config: Base test configuration

    Returns:
        EgregoraConfig with reader agent enabled and test-optimized settings
    """
    config = test_config.model_copy(deep=True)
    config.reader.enabled = True
    config.reader.comparisons_per_post = 1  # Fast tests (minimal comparisons)
    config.reader.k_factor = 32  # Standard ELO K-factor
    return config


@pytest.fixture
def enrichment_test_config(test_config):
    """Configuration with enrichment enabled for testing.

    Use this fixture for tests that involve enrichment (URL descriptions,
    media analysis, author profiling, etc.).

    Args:
        test_config: Base test configuration

    Returns:
        EgregoraConfig with enrichment enabled
    """
    # Enrichment settings will be added here when needed
    return test_config.model_copy(deep=True)


@pytest.fixture
def pipeline_test_config(test_config):
    """Configuration for full pipeline E2E tests.

    Use this fixture for tests that run the entire write pipeline.
    Slow components (reader, enrichment) are disabled for faster execution.

    Args:
        test_config: Base test configuration

    Returns:
        EgregoraConfig optimized for pipeline E2E tests
    """
    config = test_config.model_copy(deep=True)
    config.reader.enabled = False  # Disable slow components for faster tests
    # Additional pipeline-specific overrides can be added here
    return config


@pytest.fixture
def test_model_settings():
    """Model settings optimized for testing.

    Uses fast test models and avoids production API limits.

    Returns:
        ModelSettings configured for test environment
    """
    return ModelSettings(
        writer="test-writer-model",
        enricher="test-enricher-model",
        enricher_vision="test-vision-model",
        embedding="test-embedding-model",
        reader="test-reader-model",
        banner="test-banner-model",
    )


@pytest.fixture
def test_rag_settings():
    """RAG settings for unit tests (disabled by default).

    Most unit tests don't need RAG. Enable explicitly in RAG-specific tests.

    Returns:
        RAGSettings with RAG disabled and test-optimized values
    """
    return RAGSettings(
        enabled=False,
        top_k=3,  # Smaller for tests
        min_similarity_threshold=0.7,
        embedding_max_batch_size=3,  # Faster than default 100
        embedding_timeout=5.0,  # Shorter than default 60s
    )


@pytest.fixture
def test_rag_settings_enabled(test_rag_settings):
    """RAG settings with RAG enabled (for RAG tests).

    Use this fixture for tests that specifically need RAG functionality.

    Args:
        test_rag_settings: Base RAG settings fixture

    Returns:
        RAGSettings with RAG enabled
    """
    settings = test_rag_settings.model_copy(deep=True)
    settings.enabled = True
    return settings


@pytest.fixture
def minimal_config(tmp_path: Path):
    """Minimal EgregoraConfig for fast unit tests.

    Use this for unit tests that don't need full pipeline infrastructure.
    Disables slow components (RAG, enrichment, reader) by default.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        EgregoraConfig with minimal settings for unit tests
    """
    config = create_default_config(site_root=tmp_path / "site")

    # Disable slow components
    config.rag.enabled = False
    config.enrichment.enabled = False
    config.reader.enabled = False

    # Use test models (fast, no API calls)
    config.models.writer = "test-model"
    config.models.embedding = "test-embedding"

    # Fast quotas for tests
    config.quota.daily_llm_requests = 10
    config.quota.per_second_limit = 10

    return config


@pytest.fixture
def config_factory(tmp_path: Path):
    """Factory for creating customized test configs.

    Use this when you need to test specific configuration values.

    Example:
        def test_custom_timeout(config_factory):
            config = config_factory(rag__enabled=True, rag__embedding_timeout=0.1)
            assert config.rag.enabled is True
            assert config.rag.embedding_timeout == 0.1

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Factory function that creates EgregoraConfig with kwargs
    """

    def _factory(**overrides):
        config = create_default_config(site_root=tmp_path / "site")

        # Apply overrides using __ syntax for nested settings
        # Example: rag__enabled=True -> config.rag.enabled = True
        for key, value in overrides.items():
            parts = key.split("__")
            obj = config
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)

        return config

    return _factory
