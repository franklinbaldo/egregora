"""Common test configuration and fixtures."""

import shutil
import warnings
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.e2e.test_config import DateConfig, TimeoutConfig, TimezoneConfig, WindowConfig

# Suppress Pydantic V2 warnings about fields not being initialized
# (Common in tests when using mocks or partial models)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")


@pytest.fixture
def gemini_api_key(monkeypatch):
    """Provide a mock Gemini API key."""
    monkeypatch.setenv("GOOGLE_API_KEY", "mock-key-for-testing")
    return "mock-key-for-testing"


@pytest.fixture
def clean_env(monkeypatch):
    """Ensure environment is clean of API keys for specific tests."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


@pytest.fixture
def mock_batch_client(monkeypatch):
    """Mock Gemini batch client to prevent actual API calls."""
    return MagicMock()
    # Mock batch operations if needed


@pytest.fixture
def mocked_writer_agent(writer_test_agent):
    """
    Alias for writer_test_agent to match E2E test expectations.
    """
    return writer_test_agent


@pytest.fixture
def mock_vector_store(monkeypatch):
    """Mock RAG vector store to prevent LanceDB/DuckDB creation."""
    # We use a simple list to track indexed documents instead of a full mock class
    indexed_documents = []

    # Define mock functions that match the egress API of egregora.rag
    def mock_index_documents(documents, **kwargs):
        indexed_documents.extend(documents)
        return len(documents)

    def mock_search(query, **kwargs):
        return SimpleNamespace(hits=[])

    # Patch the RAG module functions
    monkeypatch.setattr("egregora.rag.index_documents", mock_index_documents)
    monkeypatch.setattr("egregora.rag.search", mock_search)

    # Also patch where it's imported in pipelines.write
    monkeypatch.setattr(
        "egregora.orchestration.pipelines.write.index_documents", mock_index_documents, raising=False
    )

    # Patch where search is used in writer_helpers
    monkeypatch.setattr("egregora.agents.writer_helpers.search", mock_search, raising=False)

    # Return the list so tests can verify what was indexed
    return indexed_documents


@pytest.fixture
def temp_site_dir(tmp_path):
    """Create a temporary site directory."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    yield site_dir
    # Cleanup
    if site_dir.exists():
        shutil.rmtree(site_dir)


@pytest.fixture
def llm_response_mocks():
    """Mock responses for LLM calls (enrichment, writer, etc)."""
    # Simple dictionary mock. In a real scenario, this might load from a JSON file.
    return {"url_enrichments": {}, "media_enrichments": {}, "writer_post": "Mock post content"}


@pytest.fixture
def test_dates() -> DateConfig:
    """Provide test date constants."""
    return DateConfig()


@pytest.fixture
def test_timezones() -> TimezoneConfig:
    """Provide timezone constants."""
    return TimezoneConfig()


@pytest.fixture
def test_timeouts() -> TimeoutConfig:
    """Provide timeout constants for tests."""
    return TimeoutConfig()


@pytest.fixture
def window_configs() -> WindowConfig:
    """Provide windowing configuration constants."""
    return WindowConfig()


@pytest.fixture(autouse=True)
def mock_profile_agent(monkeypatch):
    """Mock the profile agent's LLM call to prevent real API requests."""
    try:
        from egregora.agents.profile import generator
        from egregora.agents.profile.generator import ProfileUpdateDecision
    except ImportError:
        # Graceful fallback if module path changes or missing deps
        return

    async def _mock_decision(*args, **kwargs):
        return ProfileUpdateDecision(
            significant=True,
            content="# Profile Update\n\nThis is a mock profile update.",
        )

    monkeypatch.setattr(generator, "_call_llm_decision", _mock_decision, raising=False)
