import duckdb

from egregora.database.duckdb_manager import DuckDBStorageManager

# We will define the migration function in this module later
# from egregora.database.migration import migrate_database

def test_migrate_documents_table_adds_missing_columns():
    """
    Test that the migration script correctly adds 'doc_type' and 'extensions'
    columns to an existing 'documents' table that lacks them.
    """
    # 1. Setup: Create a raw DuckDB connection (in-memory)
    conn = duckdb.connect(":memory:")

    # 2. Simulate "Old" Schema (missing doc_type, extensions)
    # We create a table that resembles the core Atom parts of UNIFIED_SCHEMA but without the new fields
    conn.execute("""
        CREATE TABLE documents (
            id VARCHAR PRIMARY KEY,
            title VARCHAR,
            updated TIMESTAMP,
            content VARCHAR
        )
    """)

    # Insert some legacy data
    conn.execute("""
        INSERT INTO documents (id, title, updated, content)
        VALUES ('doc-1', 'Legacy Doc', '2023-01-01 12:00:00', 'Some content')
    """)

    # Verify pre-condition: columns should not exist
    columns = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    assert "doc_type" not in columns
    assert "extensions" not in columns

    # 3. Action: Run Migration
    # We haven't implemented this yet, so we'll import it inside the test or expect it to fail
    from egregora.database.migration import migrate_database

    manager = DuckDBStorageManager.from_connection(conn)
    migrate_database(manager)

    # 4. Assertion: Columns should exist now
    columns_after = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    assert "doc_type" in columns_after
    assert "extensions" in columns_after

    # 5. Assertion: Data integrity and default values
    # Check that the legacy row still exists and has defaults populated
    row = conn.execute("SELECT doc_type, extensions FROM documents WHERE id = 'doc-1'").fetchone()

    # We expect some default value for non-nullable columns.
    # For doc_type, maybe 'post' or 'legacy'? UNIFIED_SCHEMA says nullable=False.
    # For extensions, likely '{}' (empty json).

    doc_type, extensions = row
    assert doc_type is not None # Should have a default
    assert extensions is not None # Should have a default (e.g., '{}')
