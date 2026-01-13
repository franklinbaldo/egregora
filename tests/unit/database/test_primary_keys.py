"""Tests for database schema primary key constraints."""

import uuid

import duckdb
import pytest

from egregora.database.init import initialize_database


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


def test_initialize_database_adds_primary_keys(duckdb_conn):
    """Verify that the main initializer adds the primary key constraints.

    This is the integration test that will pass once the fix is in place.
    """
    # Arrange
    initialize_database(duckdb_conn)
    doc_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    # Act & Assert for documents
    duckdb_conn.execute(
        """
            INSERT INTO documents (id, doc_type, status, extensions, content, source_checksum, created_at)
            VALUES (?, 'type', 'draft', '{}', 'content', 'checksum', NOW())
        """,
        (doc_id,)
    )
    with pytest.raises(duckdb.ConstraintException, match="violates primary key constraint"):
        duckdb_conn.execute(
        """
            INSERT INTO documents (id, doc_type, status, extensions, content, source_checksum, created_at)
            VALUES (?, 'type', 'draft', '{}', 'content', 'checksum', NOW())
        """,
        (doc_id,)
    )

    # Act & Assert for tasks
    duckdb_conn.execute(
        """
            INSERT INTO tasks (task_id, task_type, status, payload, created_at)
            VALUES (?, 'task', 'pending', '{}', NOW())
        """,
        (task_id,)
    )
    with pytest.raises(duckdb.ConstraintException, match="violates primary key constraint"):
        duckdb_conn.execute(
        """
            INSERT INTO tasks (task_id, task_type, status, payload, created_at)
            VALUES (?, 'task', 'pending', '{}', NOW())
        """,
        (task_id,)
    )
