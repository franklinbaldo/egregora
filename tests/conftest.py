from __future__ import annotations

import sys
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


# Imports below require sys.path setup above
from egregora.data_primitives import GroupSlug
from egregora.input_adapters.whatsapp import WhatsAppExport, discover_chat_file
from egregora.utils.zip import validate_zip_contents
from tests.utils.mock_batch_client import MockGeminiClient
from tests.utils.pydantic_test_models import MockEmbeddingModel, install_writer_test_model


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
        "egregora.enrichment.runners.make_url_agent",
        lambda model, prompts_dir=None: _stub_url_agent(model, prompts_dir),
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.enrichment.runners.make_media_agent",
        lambda model, prompts_dir=None: _stub_media_agent(model, prompts_dir),
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.enrichment.runners.run_url_enrichment",
        lambda agent, url, prompts_dir=None: _stub_url_run(agent, url, prompts_dir),
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.enrichment.runners.run_media_enrichment",
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
            process_whatsapp_export(..., options=WhatsAppProcessOptions())
    """
    # Patch genai.Client - this is the main client used everywhere
    monkeypatch.setattr(
        "google.genai.Client",
        MockGeminiClient,
    )
    # Patch where genai is imported in egregora modules
    monkeypatch.setattr(
        "egregora.orchestration.write_pipeline.genai.Client",
        MockGeminiClient,
    )

    return MockGeminiClient


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
# Centralized Configuration Fixtures
# =============================================================================
# See: docs/testing/config_refactoring_plan.md for design rationale


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
    from egregora.config.settings import create_default_config

    # Create site root in tmp_path for test isolation
    site_root = tmp_path / "site"
    site_root.mkdir(parents=True, exist_ok=True)

    # Create default config with test site_root
    config = create_default_config(site_root=site_root)

    return config


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
    config = test_config.model_copy(deep=True)
    # Enrichment settings will be added here when needed
    return config


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
