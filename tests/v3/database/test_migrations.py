# tests/v3/database/test_migrations.py

import ibis
import pytest
import ibis.expr.datatypes as dt
import pandas as pd

# This import will fail initially, which is expected for TDD
from egregora.database.migrations import migrate_documents_table, migrate_to_unified_schema
from egregora.database.schemas import UNIFIED_SCHEMA


@pytest.fixture(scope="function")
def db_con():
    """Provides a clean, in-memory DuckDB Ibis connection for tests."""
    con = ibis.duckdb.connect()
    yield con
    # No need to close in-memory connections explicitly with modern Ibis/DuckDB.


@pytest.fixture(scope="function")
def legacy_documents_con(db_con):
    """Provides a connection with a legacy 'documents' table missing V3 columns."""
    # A simplified legacy schema missing several key columns from the UNIFIED_SCHEMA
    legacy_schema = ibis.schema(
        {
            "id": dt.string,
            "title": dt.string,
            "updated": dt.Timestamp(timezone="UTC"),
            "content": dt.string,
        }
    )
    db_con.create_table("documents", schema=legacy_schema, overwrite=True)
    db_con.insert(
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
    return db_con


@pytest.fixture(scope="function")
def legacy_posts_con(db_con):
    """Provides a connection with a legacy 'posts' table."""
    schema = ibis.schema(
        {
            "id": dt.string,
            "title": dt.string,
            "date": dt.date,
            "created_at": dt.Timestamp(timezone="UTC"),
            "content": dt.string,
            "authors": dt.json,
        }
    )
    db_con.create_table("posts", schema=schema, overwrite=True)
    db_con.insert(
        "posts",
        [
            {
                "id": "post-1",
                "title": "Legacy Post",
                "date": "2025-01-01",
                "created_at": "2025-01-01T12:00:00Z",
                "content": "Content from a legacy post.",
                "authors": '["author-1"]',
            }
        ],
    )
    return db_con


@pytest.fixture(scope="function")
def legacy_profiles_con(db_con):
    """Provides a connection with a legacy 'profiles' table."""
    schema = ibis.schema(
        {"id": dt.string, "title": dt.string, "created_at": dt.Timestamp(timezone="UTC"), "summary": dt.string, "alias": dt.string}
    )
    db_con.create_table("profiles", schema=schema, overwrite=True)
    db_con.insert(
        "profiles",
        [
            {
                "id": "profile-1",
                "title": "Legacy Profile",
                "created_at": "2025-01-02T12:00:00Z",
                "summary": "A legacy profile.",
                "alias": "legacy-alias",
            }
        ],
    )
    return db_con


@pytest.fixture(scope="function")
def legacy_journals_con(db_con):
    """Provides a connection with a legacy 'journals' table."""
    schema = ibis.schema({"id": dt.string, "title": dt.string, "created_at": dt.Timestamp(timezone="UTC"), "content": dt.string})
    db_con.create_table("journals", schema=schema, overwrite=True)
    db_con.insert(
        "journals",
        [{"id": "journal-1", "title": "Legacy Journal", "created_at": "2025-01-03T12:00:00Z", "content": "Journal entry."}],
    )
    return db_con


@pytest.fixture(scope="function")
def legacy_media_con(db_con):
    """Provides a connection with a legacy 'media' table."""
    schema = ibis.schema(
        {"id": dt.string, "filename": dt.string, "created_at": dt.Timestamp(timezone="UTC"), "mime_type": dt.string, "content": dt.string}
    )
    db_con.create_table("media", schema=schema, overwrite=True)
    db_con.insert(
        "media",
        [
            {
                "id": "media-1",
                "filename": "legacy-image.jpg",
                "created_at": "2025-01-04T12:00:00Z",
                "mime_type": "image/jpeg",
                "content": "binary data",
            }
        ],
    )
    return db_con


def test_migrate_documents_table_adds_missing_v3_columns(legacy_documents_con):
    """
    RED Test: Verifies that the migration function adds missing columns
    to an existing 'documents' table to align it with UNIFIED_SCHEMA.
    """
    # ARRANGE: Confirm the legacy table is missing the target columns
    table = legacy_documents_con.table("documents")
    initial_columns = set(table.columns)
    assert "doc_type" not in initial_columns
    assert "published" not in initial_columns
    assert "searchable" not in initial_columns
    assert "extensions" not in initial_columns

    # ACT: Run the migration (this should fail until implemented)
    migrate_documents_table(legacy_documents_con)

    # ASSERT: Check that the columns now exist
    migrated_table = legacy_documents_con.table("documents")
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


def test_migrate_to_unified_schema_from_posts(legacy_posts_con):
    """Tests migration from a legacy 'posts' table."""
    migrate_to_unified_schema(legacy_posts_con)

    documents = legacy_posts_con.table("documents")
    data = documents.to_pandas()

    assert len(data) == 1
    assert data["id"].iloc[0] == "post-1"
    assert data["doc_type"].iloc[0] == "post"
    assert data["title"].iloc[0] == "Legacy Post"
    assert data["authors"].iloc[0] == ["author-1"]
    assert pd.notna(data["published"].iloc[0])


def test_migrate_to_unified_schema_from_profiles(legacy_profiles_con):
    """Tests migration from a legacy 'profiles' table."""
    migrate_to_unified_schema(legacy_profiles_con)

    documents = legacy_profiles_con.table("documents")
    data = documents.to_pandas()

    assert len(data) == 1
    assert data["id"].iloc[0] == "profile-1"
    assert data["doc_type"].iloc[0] == "profile"
    assert data["title"].iloc[0] == "Legacy Profile"
    assert data["summary"].iloc[0] == "A legacy profile."
    assert data["internal_metadata"].iloc[0] == {"alias": "legacy-alias"}


def test_migrate_to_unified_schema_from_journals(legacy_journals_con):
    """Tests migration from a legacy 'journals' table."""
    migrate_to_unified_schema(legacy_journals_con)

    documents = legacy_journals_con.table("documents")
    data = documents.to_pandas()

    assert len(data) == 1
    assert data["id"].iloc[0] == "journal-1"
    assert data["doc_type"].iloc[0] == "journal"


def test_migrate_to_unified_schema_from_media(legacy_media_con):
    """Tests migration from a legacy 'media' table."""
    migrate_to_unified_schema(legacy_media_con)

    documents = legacy_media_con.table("documents")
    data = documents.to_pandas()

    assert len(data) == 1
    assert data["id"].iloc[0] == "media-1"
    assert data["doc_type"].iloc[0] == "media"
    assert data["title"].iloc[0] == "legacy-image.jpg"
    assert data["content_type"].iloc[0] == "image/jpeg"


def test_migrate_to_unified_schema_is_idempotent(legacy_posts_con):
    """Tests that the migration does not run if 'documents' table exists."""
    # Run migration once
    migrate_to_unified_schema(legacy_posts_con)
    count_after_first_run = legacy_posts_con.table("documents").count().execute()
    assert count_after_first_run == 1

    # Run migration again
    migrate_to_unified_schema(legacy_posts_con)
    count_after_second_run = legacy_posts_con.table("documents").count().execute()

    # The count should not change
    assert count_after_second_run == count_after_first_run


def test_migrate_to_unified_schema_handles_missing_tables(legacy_posts_con):
    """Tests that migration runs successfully even if some legacy tables are missing."""
    # At this point, only 'posts' table exists.
    # The migration should run without errors.
    migrate_to_unified_schema(legacy_posts_con)

    documents = legacy_posts_con.table("documents")
    assert documents.count().execute() == 1
    # Verify it's the post data
    data = documents.to_pandas()
    assert data["id"].iloc[0] == "post-1"
