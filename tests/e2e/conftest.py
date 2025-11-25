"""Shared fixtures and configuration for e2e tests."""

from __future__ import annotations

import gc
import shutil
import time
from collections.abc import Iterator
from pathlib import Path

import pytest


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
    db_path = tmp_path / f"test_{timestamp}.duckdb"
    return db_path
