"""Tests for journal schema constraints."""

from datetime import datetime, timedelta

import duckdb
import pytest

from egregora.database.schemas import (
    JOURNALS_SCHEMA,
    create_table_if_not_exists,
    get_table_check_constraints,
)


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


class TestJournalsSchemaConstraints:
    """Test constraints for the journals table."""

    def test_journals_window_check_constraint_allows_valid_range(self, duckdb_conn):
        """Verify that journals.window_end >= window_start is accepted."""
        # Arrange
        constraints = get_table_check_constraints("journals")
        create_table_if_not_exists(duckdb_conn, "journals", JOURNALS_SCHEMA, check_constraints=constraints)

        # Act
        now = datetime.now()
        duckdb_conn.execute(
            """
            INSERT INTO journals (id, content, created_at, source_checksum,
                                  title, window_start, window_end)
            VALUES (?, 'content', CURRENT_TIMESTAMP, 'checksum',
                    'Journal 1', ?, ?)
            """,
            ("j1", now, now + timedelta(hours=1)),
        )

        # Assert
        result = duckdb_conn.execute("SELECT COUNT(*) FROM journals").fetchone()
        assert result[0] == 1

    def test_journals_window_check_constraint_rejects_invalid_range(self, duckdb_conn):
        """Verify that journals.window_end < window_start is rejected."""
        # Arrange
        constraints = get_table_check_constraints("journals")
        create_table_if_not_exists(duckdb_conn, "journals", JOURNALS_SCHEMA, check_constraints=constraints)

        # Act & Assert
        now = datetime.now()
        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO journals (id, content, created_at, source_checksum,
                                      title, window_start, window_end)
                VALUES (?, 'content', CURRENT_TIMESTAMP, 'checksum',
                        'Journal 2', ?, ?)
                """,
                ("j2", now, now - timedelta(hours=1)),
            )
