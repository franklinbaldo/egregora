import duckdb
import pytest
from egregora.database.ir_schema import create_table_if_not_exists, UNIFIED_SCHEMA
from egregora.database.migrations import migrate_documents_table
import ibis
import ibis.expr.datatypes as dt

# Define an "Old" schema simulating V2/V2.5 state
# Missing: doc_type, extensions, internal_metadata, status
OLD_DOCUMENTS_SCHEMA = ibis.schema(
    {
        "id": dt.String(nullable=False),
        "title": dt.String(nullable=False),
        "updated": dt.Timestamp(timezone="UTC", nullable=False),
        "published": dt.Timestamp(timezone="UTC", nullable=True),
        "links": dt.JSON(nullable=False),
        "authors": dt.JSON(nullable=False),
        "contributors": dt.JSON(nullable=False),
        "categories": dt.JSON(nullable=False),
        "summary": dt.String(nullable=True),
        "content": dt.String(nullable=True),
        "content_type": dt.String(nullable=True),
        "source": dt.JSON(nullable=True),
        "in_reply_to": dt.JSON(nullable=True),
    }
)

def test_migrate_documents_table_adds_columns():
    """Test that migration adds missing columns to the documents table."""
    conn = duckdb.connect(":memory:")

    # 1. Create table with old schema
    create_table_if_not_exists(conn, "documents", OLD_DOCUMENTS_SCHEMA)

    # Verify columns are missing
    columns = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    assert "doc_type" not in columns
    assert "extensions" not in columns
    assert "internal_metadata" not in columns
    assert "status" not in columns

    # 2. Run Migration
    migrate_documents_table(conn)

    # 3. Verify columns exist
    columns_after = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    assert "doc_type" in columns_after
    assert "extensions" in columns_after
    assert "internal_metadata" in columns_after
    assert "status" in columns_after

    # Verify default values (if applicable) or types
    # Check types
    types = {row[0]: row[1] for row in conn.execute("DESCRIBE documents").fetchall()}
    assert types["doc_type"] == "VARCHAR" # or similar
    assert types["extensions"] == "JSON"
    assert types["internal_metadata"] == "JSON"

def test_migrate_documents_table_idempotent():
    """Test that migration is safe to run multiple times."""
    conn = duckdb.connect(":memory:")
    create_table_if_not_exists(conn, "documents", UNIFIED_SCHEMA)

    # Run migration on already correct table
    migrate_documents_table(conn)

    # Should not raise error and schema should be intact
    columns_after = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    assert "doc_type" in columns_after

def test_migrate_creates_table_if_missing():
    """Test that migration creates the table if it doesn't exist."""
    conn = duckdb.connect(":memory:")

    migrate_documents_table(conn)

    tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
    assert "documents" in tables

    columns = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    assert "doc_type" in columns
