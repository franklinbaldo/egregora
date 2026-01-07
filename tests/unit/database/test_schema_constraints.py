"""Tests for database schema constraints (NOT NULL, CHECK, UNIQUE, FOREIGN KEY)."""

import duckdb
import pytest

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
    """Test constraints for the documents table."""

    def test_documents_status_check_constraint_allows_valid_values(self, duckdb_conn):
        """Verify that documents.status CHECK constraint allows valid status values."""
        # Arrange: Create documents table with constraints
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(
            duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints
        )

        # Act & Assert: Valid status values should be accepted
        valid_statuses = ["draft", "published", "archived", "pending", "completed"]
        for status in valid_statuses:
            duckdb_conn.execute(
                """
                INSERT INTO documents (id, content, created_at, source_checksum,
                                  title, slug, date, summary, authors, tags, status, doc_type)
                VALUES (?, 'test content', CURRENT_TIMESTAMP, 'checksum',
                       'Test Title', 'test-slug', CURRENT_DATE, 'Test summary',
                       ARRAY['author1'], ARRAY['tag1'], ?, ?)
                """,
                (f"doc-{status}", status, "post"),
            )

        # Verify all rows were inserted
        result = duckdb_conn.execute("SELECT COUNT(*) FROM documents").fetchone()
        assert result[0] == len(valid_statuses)

    def test_documents_status_check_constraint_rejects_invalid_values(self, duckdb_conn):
        """Verify that documents.status CHECK constraint rejects invalid status values."""
        # Arrange: Create documents table with constraints
        constraints = get_table_check_constraints("documents")
        create_table_if_not_exists(
            duckdb_conn, "documents", UNIFIED_SCHEMA, check_constraints=constraints
        )

        # Act & Assert: Invalid status values should be rejected
        invalid_statuses = ["banana", "PUBLISHED", "Draft", "", "unknown"]
        for invalid_status in invalid_statuses:
            with pytest.raises(duckdb.ConstraintException, match="CHECK constraint"):
                duckdb_conn.execute(
                    """
                    INSERT INTO documents (id, content, created_at, source_checksum,
                                      title, slug, date, summary, authors, tags, status, doc_type)
                    VALUES (?, 'test content', CURRENT_TIMESTAMP, 'checksum',
                           'Test Title', 'test-slug', CURRENT_DATE, 'Test summary',
                           ARRAY['author1'], ARRAY['tag1'], ?, ?)
                    """,
                    (f"doc-{invalid_status}", invalid_status, "post"),
                )
