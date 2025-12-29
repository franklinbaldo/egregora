import ibis
import ibis.expr.datatypes as dt
import pytest

# This function does not exist yet, so this import will fail.
from egregora.database.migrations import migrate_to_unified_schema

from egregora.database.schemas import create_table_if_not_exists

# Define the legacy schemas directly in the test for isolation
# This is what the database is expected to look like *before* the migration.
BASE_COLUMNS = {
    "id": dt.string,
    "content": dt.string,
    "created_at": dt.timestamp,
    "source_checksum": dt.string,
}

LEGACY_POSTS_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "title": dt.string,
        "slug": dt.string,
        "date": dt.date,
        "summary": dt.string,
        "authors": dt.Array(dt.string),
        "tags": dt.Array(dt.string),
        "status": dt.string,
    }
)

LEGACY_PROFILES_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "subject_uuid": dt.string,
        "title": dt.string,
        "alias": dt.string,
        "summary": dt.string,
        "avatar_url": dt.string,
        "interests": dt.Array(dt.string),
    }
)

LEGACY_JOURNALS_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "title": dt.string,
        "window_start": dt.timestamp,
        "window_end": dt.timestamp,
    }
)

LEGACY_MEDIA_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "filename": dt.string,
        "mime_type": dt.string,
        "media_type": dt.string,
        "phash": dt.string,
    }
)


@pytest.fixture
def legacy_db():
    """Sets up an in-memory DuckDB with the legacy multi-table schema."""
    con = ibis.connect("duckdb://:memory:")

    # Create legacy tables
    create_table_if_not_exists(con, "posts", LEGACY_POSTS_SCHEMA)
    create_table_if_not_exists(con, "profiles", LEGACY_PROFILES_SCHEMA)
    create_table_if_not_exists(con, "journals", LEGACY_JOURNALS_SCHEMA)
    create_table_if_not_exists(con, "media", LEGACY_MEDIA_SCHEMA)

    # Insert sample data
    con.raw_sql(
        "INSERT INTO posts (id, title, slug, date, content, created_at, source_checksum) VALUES ('post1', 'Post 1', 'post-1', '2025-01-01', 'Content 1', '2025-01-01T12:00:00Z', 'cs1')"
    )
    con.raw_sql(
        "INSERT INTO profiles (id, subject_uuid, title, alias, content, created_at, source_checksum) VALUES ('prof1', 'uuid1', 'Profile 1', 'test-alias', 'Bio 1', '2025-01-02T12:00:00Z', 'cs2')"
    )
    con.raw_sql(
        "INSERT INTO journals (id, title, content, created_at, source_checksum) VALUES ('jour1', 'Journal 1', 'Journal Content 1', '2025-01-03T12:00:00Z', 'cs3')"
    )
    con.raw_sql(
        "INSERT INTO media (id, filename, mime_type, content, created_at, source_checksum) VALUES ('media1', 'image.jpg', 'image/jpeg', 'Media Content 1', '2025-01-04T12:00:00Z', 'cs4')"
    )

    return con


def test_migration_from_legacy_schema(legacy_db):
    """
    Tests the migration from the old multi-table schema to the new unified schema.
    This test is expected to fail initially because the migration script does not exist.
    """
    # 1. (RED) Verify the initial state: `documents` table should not exist.
    assert "documents" not in legacy_db.list_tables()
    assert "posts" in legacy_db.list_tables()
    assert "profiles" in legacy_db.list_tables()
    assert "journals" in legacy_db.list_tables()
    assert "media" in legacy_db.list_tables()

    # 2. (RED) Call the migration function (this should fail).
    # The import at the top of the file will raise an ImportError.
    migrate_to_unified_schema(legacy_db)

    # 3. (GREEN) Verify the final state (these assertions will be tested later).
    assert "documents" in legacy_db.list_tables()
    documents_table = legacy_db.table("documents")
    assert documents_table.count().execute() == 4

    # Verify post data
    post_row = documents_table.filter(documents_table.id == "post1").execute()
    assert post_row.iloc[0]["doc_type"] == "post"
    assert post_row.iloc[0]["title"] == "Post 1"

    # Verify profile data and the bug fix
    profile_row = documents_table.filter(documents_table.id == "prof1").execute()
    assert profile_row.iloc[0]["doc_type"] == "profile"
    assert profile_row.iloc[0]["title"] == "Profile 1"
    assert profile_row.iloc[0]["internal_metadata"] == {"alias": "test-alias"}

    # Verify journal data
    journal_row = documents_table.filter(documents_table.id == "jour1").execute()
    assert journal_row.iloc[0]["doc_type"] == "journal"
    assert journal_row.iloc[0]["title"] == "Journal 1"

    # Verify media data
    media_row = documents_table.filter(documents_table.id == "media1").execute()
    assert media_row.iloc[0]["doc_type"] == "media"
    assert media_row.iloc[0]["title"] == "image.jpg"
    assert media_row.iloc[0]["content_type"] == "image/jpeg"
