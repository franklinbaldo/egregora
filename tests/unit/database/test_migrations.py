"""Tests for migration logic."""

from datetime import datetime, timedelta

import duckdb
import pytest

from egregora.database.migrations import migrate_journals_table
from egregora.database.schemas import JOURNALS_SCHEMA, create_table_if_not_exists


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


class TestMigrations:
    """Test schema migrations."""

    def test_migrate_journals_table_applies_constraint(self, duckdb_conn):
        """Verify that migration applies the constraint to an existing table."""
        # Arrange: Create table WITHOUT constraints initially (manually or via helper with empty constraints)
        # Note: create_table_if_not_exists uses get_table_check_constraints internally if we don't override,
        # but we can pass check_constraints={} to avoid them.
        create_table_if_not_exists(duckdb_conn, "journals", JOURNALS_SCHEMA, check_constraints={})

        # Insert some valid data
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

        # Act: Run migration
        migrate_journals_table(duckdb_conn)

        # Assert:
        # 1. Data should still be there
        count = duckdb_conn.execute("SELECT COUNT(*) FROM journals").fetchone()[0]
        assert count == 1

        # 2. Invalid data should now be rejected
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

    def test_migrate_journals_table_fails_on_existing_violations(self, duckdb_conn):
        """Verify that migration fails if existing data violates the new constraint."""
        # Arrange: Create table WITHOUT constraints
        create_table_if_not_exists(duckdb_conn, "journals", JOURNALS_SCHEMA, check_constraints={})

        # Insert INVALID data (allowed before migration)
        now = datetime.now()
        duckdb_conn.execute(
            """
            INSERT INTO journals (id, content, created_at, source_checksum,
                                  title, window_start, window_end)
            VALUES (?, 'content', CURRENT_TIMESTAMP, 'checksum',
                    'Journal Bad', ?, ?)
            """,
            ("j_bad", now, now - timedelta(hours=1)),
        )

        # Act & Assert: Migration should raise exception
        with pytest.raises(duckdb.ConstraintException):
            migrate_journals_table(duckdb_conn)

        # Verify table still exists and wasn't dropped/corrupted
        count = duckdb_conn.execute("SELECT COUNT(*) FROM journals").fetchone()[0]
        assert count == 1
