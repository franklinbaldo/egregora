# tests/v3/database/test_migrations.py

import ibis
import pytest
import ibis.expr.datatypes as dt
import pandas as pd

# This import will fail initially, which is expected for TDD
from egregora.database.migrations import migrate_documents_table
from egregora.database.schemas import UNIFIED_SCHEMA


@pytest.fixture(scope="function")
def legacy_con():
    """Provides an in-memory DuckDB Ibis connection with a legacy 'documents' table."""
    # Use the standard public API to create a clean, in-memory DuckDB connection for the test.
    con = ibis.duckdb.connect()

    # A simplified legacy schema missing several key columns from the UNIFIED_SCHEMA
    # NOTE: It's crucial to use the ibis.expr.datatypes (dt) for schema definition,
    # not raw strings, to comply with the modern Ibis API.
    legacy_schema = ibis.schema(
        {
            "id": dt.string,
            "title": dt.string,
            "updated": dt.Timestamp(timezone="UTC"),
            "content": dt.string,
            # Key missing columns to test against:
            # - published
            # - doc_type
            # - status
            # - searchable
            # - extensions
            # - internal_metadata
        }
    )

    con.create_table("documents", schema=legacy_schema, overwrite=True)

    # Insert a row to ensure data is preserved after migration
    con.insert(
        "documents",
        [
            {
                "id": "doc-1",
                "title": "My Legacy Document",
                "updated": "2025-01-15T10:00:00Z",
                "content": "This content should be preserved.",
            }
        ],
    )

    yield con

    # Teardown
    try:
        con.drop_table("documents", force=True)
    except Exception:
        pass  # Table might not exist if a test fails early
    finally:
        if hasattr(con, "con"):
            con.con.close()

def test_migrate_documents_table_adds_missing_v3_columns(legacy_con):
    """
    RED Test: Verifies that the migration function adds missing columns
    to an existing 'documents' table to align it with UNIFIED_SCHEMA.
    """
    # ARRANGE: Confirm the legacy table is missing the target columns
    table = legacy_con.table("documents")
    initial_columns = set(table.columns)
    assert "doc_type" not in initial_columns
    assert "published" not in initial_columns
    assert "searchable" not in initial_columns
    assert "extensions" not in initial_columns

    # ACT: Run the migration (this should fail until implemented)
    migrate_documents_table(legacy_con)

    # ASSERT: Check that the columns now exist
    migrated_table = legacy_con.table("documents")
    final_columns = set(migrated_table.columns)

    assert "doc_type" in final_columns
    assert "published" in final_columns
    assert "searchable" in final_columns
    assert "extensions" in final_columns

    # ASSERT: Ensure all columns from the target schema are present
    assert set(UNIFIED_SCHEMA.names).issubset(final_columns)

    # ASSERT: Verify that the original data was not lost
    data = migrated_table.to_pandas()
    assert len(data) == 1
    assert data["id"].iloc[0] == "doc-1"
    assert data["title"].iloc[0] == "My Legacy Document"

    # ASSERT: Check that newly added nullable columns have null values
    assert data["doc_type"].iloc[0] is None
    # For timestamp columns, pandas uses NaT (Not a Time) for null values.
    # The correct way to check for this is pandas.isna().
    assert pd.isna(data["published"].iloc[0])
