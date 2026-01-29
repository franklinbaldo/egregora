"""Integration test for Asset Cache schema."""

from datetime import UTC, datetime

import duckdb
import pytest

from egregora.database.init import initialize_database


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


def test_asset_cache_creation(duckdb_conn):
    """Verify that asset_cache table and indexes are created."""
    # Act
    initialize_database(duckdb_conn)

    # Assert Tables
    result = duckdb_conn.execute("SHOW TABLES").fetchall()
    tables = {row[0] for row in result}
    assert "asset_cache" in tables

    # Assert Indexes
    result_indexes = duckdb_conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'asset_cache'"
    ).fetchall()
    indexes = {row[0] for row in result_indexes}
    assert "idx_asset_cache_url" in indexes
    assert "idx_asset_cache_hash" in indexes


def test_asset_cache_insertion(duckdb_conn):
    """Verify we can insert data into asset_cache."""
    initialize_database(duckdb_conn)

    # Insert a dummy record
    ts = datetime.now(UTC)
    blob_data = b"some binary data"
    sql = """
    INSERT INTO asset_cache (url, content_hash, content_type, content, fetched_at)
    VALUES ('https://example.com/image.png', 'hash123', 'image/png', ?, ?)
    """
    duckdb_conn.execute(sql, [blob_data, ts])

    # Verify insertion
    result = duckdb_conn.execute("SELECT * FROM asset_cache").fetchall()
    assert len(result) == 1
    assert result[0][0] == "https://example.com/image.png"
    assert result[0][3] == blob_data
