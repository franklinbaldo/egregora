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
    """Mock VectorStore for RAG-enabled E2E tests.

    This creates a mock VectorStore that returns deterministic RAG results
    without requiring real embeddings or vector search.
    """

    class MockVectorStore:
        """Mock VectorStore for E2E testing."""

        def __init__(self, chunks_path: Path, storage=None):
            self.chunks_path = chunks_path
            self.parquet_path = chunks_path  # Alias for compatibility
            self.storage = storage
            self.indexed_documents = []
            self.indexed_media = []

        def index_documents(self, output_format, *, embedding_model: str):
            """Mock document indexing."""
            self.indexed_documents.append({"output_format": output_format, "model": embedding_model})
            # Return count of indexed chunks (matching real VectorStore signature)
            return 10

        def index_media(self, docs_dir: Path, *, embedding_model: str):
            """Mock media indexing."""
            self.indexed_media.append({"docs_dir": docs_dir, "model": embedding_model})
            # Return count of indexed chunks (matching real VectorStore signature)
            return 4

        def search(
            self,
            query_vec: list[float],
            top_k: int = 5,
            min_similarity_threshold: float = 0.7,
            tag_filter: list[str] | None = None,
            date_after=None,
            document_type: str | None = None,
            media_types: list[str] | None = None,
            *,
            mode: str = "ann",
            nprobe: int | None = None,
            overfetch: int | None = None,
        ):
            """Mock vector search that returns an Ibis Table."""
            import ibis
            import pandas as pd

            # Create mock search results as pandas DataFrame
            mock_results = pd.DataFrame(
                [
                    {
                        "document_id": "test-doc-1",
                        "text": "Test search result",
                        "similarity": 0.85,
                        "chunk_index": 0,
                        "document_type": "post",
                    }
                ]
            )
            # Convert to Ibis table
            return ibis.memtable(mock_results[:top_k])

        def query_media(
            self,
            query: str,
            *,
            media_types: list[str] | None = None,
            top_k: int = 5,
            min_similarity: float = 0.7,
        ) -> Iterator[dict]:
            """Return mocked media search results."""
            mock_results = [
                {
                    "document_id": "test-media-1",
                    "filename": "media/images/test-media-1.jpg",
                    "similarity": 0.92,
                    "caption": "Test image",
                    "media_type": "image",
                }
            ]
            if media_types:
                mock_results = [r for r in mock_results if r["media_type"] in media_types]
            yield from mock_results[:top_k]

        @staticmethod
        def is_available() -> bool:
            """Mock availability check."""
            return True

    # Try to patch VectorStore if RAG module exists
    try:
        from egregora.agents.shared import rag

        monkeypatch.setattr(rag, "VectorStore", MockVectorStore)

        # Also mock the embed_query function to avoid real API calls
        def mock_embed_query(query_text: str, *, model: str) -> list[float]:
            """Mock embed_query to return deterministic embedding without API calls."""
            import hashlib

            # Generate deterministic embedding from query text
            hash_val = int(hashlib.md5(query_text.encode()).hexdigest(), 16)
            import random

            random.seed(hash_val)
            return [random.random() for _ in range(768)]  # 768-dim embedding

        monkeypatch.setattr("egregora.agents.shared.rag.embedder.embed_query_text", mock_embed_query)
    except (ImportError, AttributeError):
        # RAG module may not exist yet - this is optional
        pass

    return MockVectorStore


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
