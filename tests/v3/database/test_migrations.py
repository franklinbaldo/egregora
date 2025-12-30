import ibis
import ibis.expr.datatypes as dt
import pytest
import pandas as pd

from egregora.database.migrations import migrate_documents_table


# A simplified legacy schema that is missing the V3 columns.
LEGACY_DOCUMENTS_SCHEMA = ibis.schema(
    {
        "id": dt.string,
        "content": dt.string,
        "created_at": dt.timestamp,
        "source_checksum": dt.string,
        "title": dt.string,
    }
)


def test_migrate_documents_table_adds_v3_columns():
    """Verify that the migration adds missing V3 columns idempotently."""
    # 1. Setup: Create an in-memory DuckDB with a legacy `documents` table.
    con = ibis.connect("duckdb://")

    con.create_table("documents", schema=LEGACY_DOCUMENTS_SCHEMA)

    legacy_data = pd.DataFrame([
        {
            "id": "legacy-doc-1",
            "content": "This is a test document.",
            "created_at": pd.to_datetime("2025-01-01T12:00:00Z"),
            "source_checksum": "abc",
            "title": "Legacy Doc",
        }
    ])
    con.insert("documents", legacy_data)

    # 2. Verify Pre-conditions: V3 columns should NOT exist yet.
    table_before = con.table("documents")
    assert "doc_type" not in table_before.columns
    assert "extensions" not in table_before.columns

    # 3. Action: Run the migration
    migrate_documents_table(con)

    # 4. Verify Post-conditions: V3 columns should now exist.
    table_after = con.table("documents")

    assert "doc_type" in table_after.columns
    assert "extensions" in table_after.columns
    assert "internal_metadata" in table_after.columns

    # Verify that existing data was preserved
    result = table_after.limit(1).execute()
    assert len(result) == 1
    assert result["id"][0] == "legacy-doc-1"

    # Verify that new columns have a default value (e.g., NULL)
    assert result["doc_type"][0] is None
