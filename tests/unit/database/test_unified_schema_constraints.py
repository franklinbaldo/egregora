"""Tests for constraints on the unified 'documents' table."""

import duckdb
import pytest

from egregora.database.migrations import migrate_documents_table
from egregora.database.schemas import (
    UNIFIED_SCHEMA,
    create_table_if_not_exists,
    get_table_check_constraints,
)


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


class TestDocumentsSchemaConstraints:
    """Test constraints for the unified documents table."""

    def test_post_constraints_enforced(self, duckdb_conn):
        """Verify that 'post' documents must have title, slug, and status."""
        # Arrange
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints)

        # Act & Assert: Insert post without title should fail
        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, content, status, title, slug)
                VALUES ('1', 'post', 'content', 'published', NULL, 'slug')
                """
            )

    def test_profile_constraints_enforced(self, duckdb_conn):
        """Verify that 'profile' documents must have title and subject_uuid."""
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints)

        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, content, status, title, subject_uuid)
                VALUES ('2', 'profile', 'content', 'published', NULL, 'uuid')
                """
            )

    def test_journal_constraints_enforced(self, duckdb_conn):
        """Verify that 'journal' documents must have title, window_start, window_end."""
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints)

        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, content, status, title, window_start, window_end)
                VALUES ('3', 'journal', 'content', 'published', 'Journal', NULL, CURRENT_TIMESTAMP)
                """
            )

    def test_migration_adds_constraints(self, duckdb_conn):
        """Verify that migration applies constraints to existing table."""
        # Arrange: Create table WITHOUT constraints
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=None)

        # Verify no constraints initially (should succeed)
        duckdb_conn.execute(
            """
            INSERT INTO documents (id, doc_type, content, status, title, slug)
            VALUES ('old', 'post', 'content', 'published', NULL, 'slug')
            """
        )
        # Delete the invalid row so migration can succeed?
        # If I leave it, migration might fail on "CHECK constraint violation"?
        # Migration does: INSERT INTO temp SELECT ...
        # If constraints are on temp table, invalid data will cause migration to fail.
        # This is expected behavior (strict migration).
        # Let's verify that migration FAILS with invalid data.

        with pytest.raises(duckdb.ConstraintException):
            migrate_documents_table(duckdb_conn)

        # Clear data
        duckdb_conn.execute("DELETE FROM documents")

        # Run migration on empty valid table
        migrate_documents_table(duckdb_conn)

        # Now constraints should be enforced
        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, content, status, title, slug)
                VALUES ('new', 'post', 'content', 'published', NULL, 'slug')
                """
            )
