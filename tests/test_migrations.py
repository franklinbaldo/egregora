

import duckdb

from egregora.database.ir_schema import UNIFIED_SCHEMA
from egregora.database.migrations import migrate_documents_table


def test_migrate_documents_table_adds_missing_columns():
    """Test that migrate_documents_table adds missing columns to an existing table."""
    conn = duckdb.connect(":memory:")

    # 1. Create a "legacy" table (missing 'doc_type', 'extensions', 'status')
    conn.execute("""
        CREATE TABLE documents (
            id VARCHAR,
            title VARCHAR,
            updated TIMESTAMP,
            content VARCHAR,
            links JSON,
            authors JSON,
            contributors JSON,
            categories JSON
        )
    """)

    # Insert some data
    conn.execute("""
        INSERT INTO documents (id, title, updated, content, links, authors, contributors, categories)
        VALUES ('1', 'Test Doc', '2023-01-01 00:00:00', 'Content', '[]', '[]', '[]', '[]')
    """)

    # Verify initial schema
    columns = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    assert "doc_type" not in columns
    assert "extensions" not in columns
    assert "status" not in columns

    # 2. Run Migration
    migrate_documents_table(conn)

    # 3. Verify Schema Updated
    columns = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    assert "doc_type" in columns
    assert "extensions" in columns
    assert "status" in columns
    assert "internal_metadata" in columns

    # 4. Verify Data Preserved and Defaults Applied
    row = conn.execute("SELECT * FROM documents WHERE id = '1'").fetchone()
    # Fetch dict of column name -> value
    col_names = [desc[0] for desc in conn.description]
    row_dict = dict(zip(col_names, row, strict=False))

    assert row_dict["id"] == "1"
    assert row_dict["title"] == "Test Doc"
    assert row_dict["doc_type"] == "post"  # Default
    assert row_dict["status"] == "published" # Default
    # DuckDB returns JSON as string? Or as object?
    # Usually string if not strictly typed, but let's check.
    # Ibis types map to DuckDB JSON type.
    # The default value string in migration was "'{}'"
    # DuckDB might return it as a string representation of JSON.
    assert row_dict["extensions"] == "{}"

    conn.close()

def test_migrate_documents_table_creates_fresh():
    """Test that migrate_documents_table creates the table if it doesn't exist."""
    conn = duckdb.connect(":memory:")

    # Table does not exist

    # Run Migration
    migrate_documents_table(conn)

    # Verify Table Exists
    tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
    assert "documents" in tables

    # Verify Schema matches UNIFIED_SCHEMA roughly
    columns = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    expected_cols = UNIFIED_SCHEMA.names
    for col in expected_cols:
        assert col in columns

    conn.close()
