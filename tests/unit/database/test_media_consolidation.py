"""Tests for consolidating media table into documents table."""

import duckdb

from egregora.database.migrations import migrate_media_table
from egregora.database.schemas import UNIFIED_SCHEMA, create_table_if_not_exists, get_table_check_constraints


def test_media_consolidation_migration():
    """Test that data from the legacy media table is migrated to documents and media table is dropped."""
    # Setup legacy state: documents table (v3) + media table (legacy)
    conn = duckdb.connect(":memory:")

    # Create documents table (simulate pre-migration state)
    # We create it with the UNIFIED_SCHEMA but maybe without the new constraint yet
    # But for this test, we care about data movement.
    create_table_if_not_exists(
        conn,
        "documents",
        UNIFIED_SCHEMA,
        check_constraints=get_table_check_constraints("documents"),
        primary_key="id",
    )

    # Create legacy media table
    conn.execute("""
        CREATE TABLE media (
            id VARCHAR,
            content VARCHAR,
            created_at TIMESTAMP WITH TIME ZONE,
            source_checksum VARCHAR,
            filename VARCHAR,
            mime_type VARCHAR,
            media_type VARCHAR,
            phash VARCHAR
        )
    """)

    # Insert legacy data into media
    conn.execute("""
        INSERT INTO media VALUES (
            'm1', 'blob', '2023-01-01 00:00:00+00', 'abc',
            'file.jpg', 'image/jpeg', 'image', '123'
        )
    """)

    # Verify media exists before migration
    assert "media" in [x[0] for x in conn.execute("SHOW TABLES").fetchall()]

    # Run migration
    migrate_media_table(conn)

    # Verify media table is gone
    assert "media" not in [x[0] for x in conn.execute("SHOW TABLES").fetchall()]

    # Verify data moved to documents
    rows = conn.execute("SELECT * FROM documents WHERE id='m1'").fetchall()
    assert len(rows) == 1

    # Check columns
    # We need to map columns to names to check values
    cols = [x[0] for x in conn.description]
    row_dict = dict(zip(cols, rows[0], strict=False))

    assert row_dict["doc_type"] == "media"
    assert row_dict["status"] == "published"
    assert row_dict["filename"] == "file.jpg"
    assert row_dict["media_type"] == "image"
    assert row_dict["mime_type"] == "image/jpeg"
    assert row_dict["phash"] == "123"
    assert row_dict["content"] == "blob"


def test_media_migration_idempotent():
    """Test that migration is idempotent (does nothing if media table missing)."""
    conn = duckdb.connect(":memory:")
    create_table_if_not_exists(
        conn,
        "documents",
        UNIFIED_SCHEMA,
        check_constraints=get_table_check_constraints("documents"),
        primary_key="id",
    )

    # Ensure no media table
    assert "media" not in [x[0] for x in conn.execute("SHOW TABLES").fetchall()]

    # Run migration
    migrate_media_table(conn)

    # Should still pass
    assert "media" not in [x[0] for x in conn.execute("SHOW TABLES").fetchall()]
