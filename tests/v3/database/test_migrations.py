"""Tests for V3 database schema migrations."""
from __future__ import annotations

import duckdb
import ibis
import ibis.expr.datatypes as dt
import pytest

from egregora.database.migrations import migrate_documents_table

# A simplified legacy schema that is missing the new V3 columns
LEGACY_DOCUMENTS_SCHEMA = ibis.schema(
    {
        "id": dt.string,
        "content": dt.string,
        "created_at": dt.timestamp,
        "source_checksum": dt.string,
        "title": dt.string,
    }
)


def _get_table_info(conn: duckdb.DuckDBPyConnection, table_name: str) -> dict[str, dict]:
    """Helper to get table schema info."""
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    # Returns a dict mapping column name to its info (e.g., type, nullable)
    return {row[1]: {"type": row[2], "notnull": bool(row[3])} for row in result}


def test_migrate_documents_table_from_legacy_schema():
    """Verify migration from a legacy schema to the V3 UNIFIED_SCHEMA."""
    conn = duckdb.connect(":memory:")

    # 1. 🔴 RED: Setup a legacy table
    # Use the public API to generate the SQL for table creation
    legacy_create_sql = ibis.to_sql(
        ibis.table(LEGACY_DOCUMENTS_SCHEMA, name="documents")
    )
    # ibis.to_sql() generates a SELECT, we need a CREATE TABLE statement.
    # A more direct way is needed. Let's see if ibis.schema can be used directly with duckdb
    # For now, let's build the SQL string manually for the test setup.
    # This is not ideal, but it isolates the test from Ibis internal API changes.
    columns_sql = ", ".join(f'"{name}" VARCHAR' for name in LEGACY_DOCUMENTS_SCHEMA.names)
    legacy_create_sql = f"CREATE TABLE documents ({columns_sql})"

    conn.execute(legacy_create_sql)
    conn.execute(
        "INSERT INTO documents (id, content, created_at, source_checksum, title) "
        "VALUES ('doc1', 'Legacy content', '2025-01-01 00:00:00', 'checksum1', 'Legacy Title')"
    )


    # Verify the initial state
    table_info_before = _get_table_info(conn, "documents")
    assert "doc_type" not in table_info_before
    assert "status" not in table_info_before
    assert "extensions" not in table_info_before
    assert table_info_before["title"]["notnull"] is False

    # 2. 🟢 GREEN: Run the migration
    migrate_documents_table(conn)

    # 3. 🔵 REFACTOR: Verify the final state
    table_info_after = _get_table_info(conn, "documents")

    # Check that new columns were added and have NOT NULL constraints
    assert "doc_type" in table_info_after
    assert "status" in table_info_after
    assert "extensions" in table_info_after
    assert table_info_after["doc_type"]["notnull"] is True
    assert table_info_after["status"]["notnull"] is True

    # Verify that existing data was preserved and backfilled
    result = conn.execute("SELECT * FROM documents WHERE id = 'doc1'").fetchone()
    columns = [desc[0] for desc in conn.description]
    result_dict = dict(zip(columns, result))

    assert result_dict["content"] == "Legacy content"
    assert result_dict["title"] == "Legacy Title"
    assert result_dict["doc_type"] == "note"  # Check default backfill value
    assert result_dict["status"] == "draft"  # Check default backfill value

    # Verify NOT NULL constraint is enforced on new inserts
    with pytest.raises(duckdb.ConstraintException, match="NOT NULL constraint failed"):
        conn.execute("INSERT INTO documents (id, doc_type) VALUES ('doc2', NULL)")

    with pytest.raises(duckdb.ConstraintException, match="NOT NULL constraint failed"):
        conn.execute("INSERT INTO documents (id, status) VALUES ('doc2', NULL)")

    # Verify that a second run is idempotent (no errors)
    try:
        migrate_documents_table(conn)
    except Exception as e:
        pytest.fail(f"Idempotency check failed. Migration raised an error on second run: {e}")

    conn.close()
