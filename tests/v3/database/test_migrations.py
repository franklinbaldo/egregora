"""Tests for V3 schema migrations."""
import pytest
import ibis
import duckdb
from ibis import _, selectors
from ibis.expr import datatypes as dt

# This import will fail initially, which is expected for TDD
from egregora.database.migrations import migrate_documents_table
from egregora.database.schemas import UNIFIED_SCHEMA, ibis_to_duckdb_type


# A simplified, legacy schema representing the state *before* V3 fields were added.
LEGACY_DOCUMENTS_SCHEMA = ibis.schema(
    {
        "id": dt.string,
        "content": dt.string,
        "created_at": dt.timestamp,
        "source_checksum": dt.string,
        "title": dt.string,
        "slug": dt.string,
        "date": dt.date,
    }
)


@pytest.fixture
def legacy_db():
    """Provides an in-memory DuckDB connection with a legacy 'documents' table."""
    conn = duckdb.connect(":memory:")

    # Create a table with the old schema
    columns_sql = ", ".join(
        f"{name} {ibis_to_duckdb_type(dtype)}"
        for name, dtype in LEGACY_DOCUMENTS_SCHEMA.items()
    )
    conn.execute(f"CREATE TABLE documents ({columns_sql})")

    # Insert some legacy data
    conn.execute(
        "INSERT INTO documents (id, content, created_at, source_checksum, title, slug, date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "legacy-doc-1",
            "This is old content.",
            "2023-01-01 12:00:00",
            "checksum123",
            "Legacy Title",
            "legacy-title",
            "2023-01-01",
        ),
    )

    yield conn
    conn.close()


def get_table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> dict[str, str]:
    """Helper to get a dictionary of column names and their types."""
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    # result is a list of tuples: (cid, name, type, notnull, dflt_value, pk)
    return {row[1]: row[2].upper() for row in result}


def test_migrate_documents_table_from_legacy(legacy_db):
    """
    Verify that the migration script correctly adds V3 columns,
    backfills data, and handles constraints.
    """
    # 1. Verify initial state (V3 columns are missing)
    initial_columns = get_table_columns(legacy_db, "documents")
    assert "doc_type" not in initial_columns
    assert "status" not in initial_columns

    # 2. Run the migration
    migrate_documents_table(legacy_db)

    # 3. VERIFY: Check the final state
    final_columns = get_table_columns(legacy_db, "documents")

    # Check that new columns were added
    assert "doc_type" in final_columns
    assert "status" in final_columns

    # Verify that existing data is preserved and backfilled
    result = legacy_db.execute("SELECT * FROM documents WHERE id = 'legacy-doc-1'").fetchone()
    col_names = [desc[0] for desc in legacy_db.description]
    row_dict = dict(zip(col_names, result))

    assert row_dict["id"] == "legacy-doc-1"
    assert row_dict["title"] == "Legacy Title"
    assert row_dict["doc_type"] == "note"  # Check for backfilled value
    assert row_dict["status"] == "draft"  # Check for backfilled value

    # Verify NOT NULL constraint by trying to insert a NULL value
    with pytest.raises(duckdb.ConstraintException):
        legacy_db.execute("INSERT INTO documents (id, doc_type, status) VALUES ('new-doc', NULL, 'published')")

    with pytest.raises(duckdb.ConstraintException):
        legacy_db.execute("INSERT INTO documents (id, doc_type, status) VALUES ('new-doc', 'post', NULL)")
