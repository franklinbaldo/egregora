"""Integration tests for database schema indexes."""

import ibis

from egregora.database.init import initialize_database


def test_documents_indexes_are_created_successfully(tmp_path):
    """Verify that indexes are created on the documents table.

    This test initializes a fresh DuckDB database and checks the system catalog
    to ensure the expected indexes exist.
    """
    # Setup temporary database
    db_path = tmp_path / "test.db"
    con = ibis.duckdb.connect(str(db_path))

    # Initialize
    initialize_database(con)

    # Verify indexes using raw DuckDB connection
    raw_con = con.con

    # Use system view duckdb_indexes()
    indexes = raw_con.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'documents'"
    ).fetchall()

    # Flatten results (list of tuples)
    index_names = [row[0] for row in indexes]

    expected_indexes = [
        "idx_documents_type",
        "idx_documents_slug",
        "idx_documents_created",
    ]

    missing = [idx for idx in expected_indexes if idx not in index_names]

    assert not missing, f"Missing expected indexes: {missing}. Found: {index_names}"


def test_asset_cache_indexes_are_created_successfully(tmp_path):
    """Verify that indexes are created on the asset_cache table."""
    # Setup temporary database
    db_path = tmp_path / "test_assets.db"
    con = ibis.duckdb.connect(str(db_path))

    # Initialize
    initialize_database(con)

    # Verify indexes using raw DuckDB connection
    raw_con = con.con

    indexes = raw_con.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'asset_cache'"
    ).fetchall()

    index_names = [row[0] for row in indexes]

    expected_indexes = [
        "idx_asset_cache_url",
        "idx_asset_cache_hash",
        "idx_asset_cache_expires",
    ]

    missing = [idx for idx in expected_indexes if idx not in index_names]

    assert not missing, f"Missing expected indexes: {missing}. Found: {index_names}"
