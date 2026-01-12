"""Tests for database schema CHECK constraints."""

from __future__ import annotations

from typing import Any

import duckdb
import pytest

from egregora.database.init import initialize_database


@pytest.fixture
def db_conn() -> Any:
    """Fixture to provide an in-memory DuckDB connection."""
    return duckdb.connect(":memory:")


def test_tasks_status_check_constraint_rejects_invalid_values(db_conn: Any) -> None:
    """Verify tasks.status CHECK constraint rejects invalid values."""
    initialize_database(db_conn)
    with pytest.raises(duckdb.ConstraintException):
        db_conn.execute(
            "INSERT INTO tasks (task_id, task_type, status, payload, created_at) VALUES ('a', 'b', 'invalid', '{}', NOW())"
        )


def test_documents_status_check_constraint_rejects_invalid_values(db_conn: Any) -> None:
    """Verify documents.status CHECK constraint rejects invalid values."""
    initialize_database(db_conn)
    # A sample row with the minimal required fields for the test
    with pytest.raises(duckdb.ConstraintException):
        db_conn.execute(
            "INSERT INTO documents (id, content, created_at, source_checksum, doc_type, status) VALUES ('a', 'b', NOW(), 'd', 'post', 'invalid')"
        )
