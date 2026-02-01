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
                INSERT INTO documents (id, doc_type, content, status, title, slug, created_at, source_checksum)
                VALUES ('1', 'post', 'content', 'published', NULL, 'slug', CURRENT_TIMESTAMP, 'hash')
                """
            )

    def test_profile_constraints_enforced(self, duckdb_conn):
        """Verify that 'profile' documents must have title and subject_uuid."""
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints)

        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, content, status, title, subject_uuid, created_at, source_checksum)
                VALUES ('2', 'profile', 'content', 'published', NULL, 'uuid', CURRENT_TIMESTAMP, 'hash')
                """
            )

    def test_journal_constraints_enforced(self, duckdb_conn):
        """Verify that 'journal' documents must have title, window_start, window_end."""
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints)

        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, content, status, title, window_start, window_end, created_at, source_checksum)
                VALUES ('3', 'journal', 'content', 'published', 'Journal', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'hash')
                """
            )

    def test_media_constraints_enforced(self, duckdb_conn):
        """Verify that 'media' documents must have filename."""
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints)

        # Invalid Media (missing filename)
        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, content, status, filename, created_at, source_checksum)
                VALUES ('4', 'media', 'content', 'published', NULL, CURRENT_TIMESTAMP, 'hash')
                """
            )

        # Valid Media
        duckdb_conn.execute(
            """
            INSERT INTO documents (id, doc_type, content, status, filename, media_type, created_at, source_checksum)
            VALUES ('5', 'media', 'content', 'published', 'file.jpg', 'image', CURRENT_TIMESTAMP, 'hash')
            """
        )

    def test_migration_adds_constraints(self, duckdb_conn):
        """Verify that migration applies constraints to existing table."""
        # Arrange: Create table WITHOUT constraints
        create_table_if_not_exists(duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=None)

        # Verify no constraints initially (should succeed)
        duckdb_conn.execute(
            """
            INSERT INTO documents (id, doc_type, content, status, title, slug, created_at, source_checksum)
            VALUES ('old', 'post', 'content', 'published', NULL, 'slug', CURRENT_TIMESTAMP, 'hash')
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
                INSERT INTO documents (id, doc_type, content, status, title, slug, created_at, source_checksum)
                VALUES ('new', 'post', 'content', 'published', NULL, 'slug', CURRENT_TIMESTAMP, 'hash')
                """
            )

    def test_migration_applies_missing_constraints(self, duckdb_conn):
        """Verify that migration runs if some constraints are missing, even if others exist."""
        # 1. Arrange: Create table with ONLY ONE constraint (simulating old schema)
        # We manually pass a subset of constraints
        full_constraints = get_table_check_constraints("documents")
        partial_constraints = {"chk_doc_post_status": full_constraints["chk_doc_post_status"]}
        # Ensure we are testing what we think we are: 'chk_doc_post_req' is MISSING.
        assert "chk_doc_post_req" not in partial_constraints
        assert "chk_doc_post_req" in full_constraints

        create_table_if_not_exists(
            duckdb_conn,
            "documents",
            UNIFIED_SCHEMA,
            check_constraints=partial_constraints,
            overwrite=True,
        )

        # Verify we can currently violate the MISSING constraint
        # Insert a post without a title (should fail if 'chk_doc_post_req' existed, but succeeds now)
        duckdb_conn.execute(
            """
            INSERT INTO documents (id, doc_type, content, status, title, slug, created_at, source_checksum)
            VALUES ('1', 'post', 'valid content', 'published', NULL, 'slug', CURRENT_TIMESTAMP, 'hash')
            """
        )

        # Clean up the row so migration can succeed (since migration enforces validity)
        duckdb_conn.execute("DELETE FROM documents")

        # 2. Act: Run migration
        migrate_documents_table(duckdb_conn)

        # 3. Assert: The MISSING constraint should now be enforced
        # Attempt to insert the same invalid row again. It should fail now.
        with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, doc_type, content, status, title, slug, created_at, source_checksum)
                VALUES ('2', 'post', 'valid content', 'published', NULL, 'slug', CURRENT_TIMESTAMP, 'hash')
                """
            )
