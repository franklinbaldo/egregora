"""Shared fixtures and configuration for e2e tests."""

from __future__ import annotations

import gc
import shutil
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.e2e.test_config import TestDates, TestTimeouts, TestTimezones, WindowConfig


@pytest.fixture(autouse=True)
def cleanup_temp_files(tmp_path: Path) -> Iterator[None]:
    """Ensure temporary files are cleaned up after each test.

    This fixture runs automatically for all e2e tests to prevent
    resource leaks and test interference.
    """
    yield

    # Force garbage collection to close any open file handles
    gc.collect()

    # Small delay to allow OS to release file handles
    time.sleep(0.1)

    # Clean up any remaining temp files (best effort)
    try:
        if tmp_path.exists():
            for item in tmp_path.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                except (OSError, PermissionError):
                    # Ignore cleanup errors - they shouldn't fail the test
                    pass
    except Exception:
        # Ignore any cleanup errors
        pass


@pytest.fixture
def isolated_temp_dir(tmp_path: Path) -> Path:
    """Create an isolated temporary directory for tests that need clean state.

    This is useful for tests that create databases or other stateful resources
    that might interfere with subsequent tests.
    """
    test_dir = tmp_path / "isolated_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture
def test_timeout() -> float:
    """Default timeout for e2e tests in seconds.

    Tests should fail fast if they hang to avoid blocking CI.
    """
    return 60.0  # 60 seconds default timeout


@pytest.fixture
def ensure_db_cleanup() -> Iterator[None]:
    """Ensure all database connections are properly closed after tests.

    This fixture helps prevent "database file with different configuration"
    errors by forcing cleanup and a small delay for OS to release locks.
    """
    yield

    # Force Python garbage collection to close any lingering connections
    gc.collect()

    # Give OS time to release file locks (especially important on Windows)
    time.sleep(0.05)


@pytest.fixture
def clean_duckdb_path(tmp_path: Path) -> Path:
    """Create a clean DuckDB database path with guaranteed uniqueness.

    Returns a path that includes a timestamp to ensure no conflicts
    between test runs or parallel executions.
    """
    import time

    timestamp = int(time.time() * 1000000)  # Microsecond precision
    return tmp_path / f"test_{timestamp}.duckdb"


# =============================================================================
# Test Configuration Fixtures
# =============================================================================


@pytest.fixture
def test_timeouts() -> TestTimeouts:
    """Provide timeout constants for tests."""
    return TestTimeouts()


@pytest.fixture
def test_dates() -> TestDates:
    """Provide test date constants."""
    return TestDates()


@pytest.fixture
def window_configs() -> WindowConfig:
    """Provide windowing configuration constants."""
    return WindowConfig()


@pytest.fixture
def test_timezones() -> TestTimezones:
    """Provide timezone constants."""
    return TestTimezones()


# =============================================================================
# E2E Pipeline Testing Fixtures
# =============================================================================


@pytest.fixture
def llm_response_mocks(monkeypatch):
    """Inject handcrafted LLM responses for deterministic E2E testing.

    This fixture patches the enrichment agents to return pre-constructed,
    realistic responses from the whatsapp_sample fixture.
    """
    from tests.e2e.mocks.enrichment_mocks import (
        async_mock_media_enrichment,
        async_mock_url_enrichment,
    )
    from tests.e2e.mocks.llm_responses import (
        FIXTURE_MEDIA_ENRICHMENTS,
        FIXTURE_URL_ENRICHMENTS,
        FIXTURE_WRITER_POST,
    )

    # Patch enrichment functions
    # Note: These paths may need adjustment based on actual implementation
    try:
        monkeypatch.setattr(
            "egregora.agents.enricher._run_url_enrichment_async",
            async_mock_url_enrichment,
        )
    except AttributeError:
        # Enrichment implementation may vary - this is optional
        pass

    try:
        monkeypatch.setattr(
            "egregora.agents.enricher._run_media_enrichment_async",
            async_mock_media_enrichment,
        )
    except AttributeError:
        # Enrichment implementation may vary - this is optional
        pass

    return {
        "url_enrichments": FIXTURE_URL_ENRICHMENTS,
        "media_enrichments": FIXTURE_MEDIA_ENRICHMENTS,
        "writer_post": FIXTURE_WRITER_POST,
    }


@pytest.fixture
def mock_vector_store(monkeypatch):
    """Mock RAG functions for E2E tests.

    This mocks the new egregora.rag API (index_documents and search) to return
    deterministic results without requiring real embeddings or vector search.
    """
    from egregora.rag import RAGHit, RAGQueryResponse

    # Track what's been indexed for assertions
    indexed_docs = []

    def mock_index_documents(documents):
        """Mock document indexing."""
        indexed_docs.extend(documents)
        # Silently succeed - indexing is non-critical

    def mock_search(request):
        """Mock RAG search that returns deterministic results."""
        # Return mock results
        hits = [
            RAGHit(
                chunk_id="test-chunk-1",
                text="This is a test document about AI and machine learning.",
                score=0.85,
                metadata={"document_type": "POST", "slug": "test-post"},
            )
        ]
        return RAGQueryResponse(hits=hits[: request.top_k])

    # Patch the new RAG API
    try:
        import egregora.rag

        monkeypatch.setattr(egregora.rag, "index_documents", mock_index_documents)
        monkeypatch.setattr(egregora.rag, "search", mock_search)
    except (ImportError, AttributeError):
        # RAG module may not exist yet - this is optional
        pass

    # Return the indexed_docs list for test assertions
    return indexed_docs


@pytest.fixture
def mocked_writer_agent(monkeypatch):
    """Mock writer agent using Pydantic-AI TestModel.

    This fixture integrates with the existing install_writer_test_model utility
    to provide deterministic writer agent responses for E2E tests.
    """
    from tests.utils.pydantic_test_models import install_writer_test_model

    # Install deterministic writer that avoids network calls
    captured_windows = []
    install_writer_test_model(monkeypatch, captured_windows)

    return {"captured_windows": captured_windows}
