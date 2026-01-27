"""Integration test for database indexes."""

import duckdb
import pytest

from egregora.database.init import initialize_database


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


def test_documents_indexes_created(duckdb_conn):
    """Verify that expected indexes are created on the unified documents table."""
    # Act
    initialize_database(duckdb_conn)

    # Assert
    # Query system view for indexes on 'documents' table
    # duckdb_indexes() columns: database_name, schema_name, table_name, index_name, column_names, etc.
    result = duckdb_conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'documents'"
    ).fetchall()

    indexes = {row[0] for row in result}

    expected_indexes = {
        "idx_documents_type",
        "idx_documents_slug",
        "idx_documents_created",
        "idx_documents_status",
    }

    assert expected_indexes.issubset(indexes), f"Missing indexes. Found: {indexes}"
