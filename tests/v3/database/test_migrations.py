"""Tests for the V3 database schema migration."""

from datetime import date, datetime, timezone

import ibis
import pytest
from ibis import _

from egregora.database.migrations import migrate_to_unified_schema, migrate_documents_table
from egregora.database.schemas import (
    POSTS_SCHEMA,
    PROFILES_SCHEMA,
    JOURNALS_SCHEMA,
    MEDIA_SCHEMA,
    create_table_if_not_exists,
)


@pytest.fixture
def v2_db_conn():
    """Provides an in-memory DuckDB Ibis connection with V2 tables."""
    con = ibis.duckdb.connect(":memory:")
    create_table_if_not_exists(con, "posts", POSTS_SCHEMA)
    create_table_if_not_exists(con, "profiles", PROFILES_SCHEMA)
    create_table_if_not_exists(con, "journals", JOURNALS_SCHEMA)
    create_table_if_not_exists(con, "media", MEDIA_SCHEMA)

    # Populate with some data
    posts_data = {
        "id": ["post1"],
        "content": ["Post content"],
        "created_at": [datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)],
        "source_checksum": ["abc"],
        "title": ["Post Title"],
        "slug": ["post-title"],
        "date": [date(2023, 1, 1)],
        "summary": ["A summary"],
        "authors": [["author1"]],
        "tags": [["tag1"]],
        "status": ["published"],
    }
    con.insert("posts", ibis.memtable(posts_data, schema=POSTS_SCHEMA))

    profiles_data = {
        "id": ["profile1"],
        "content": ["Profile bio"],
        "created_at": [datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc)],
        "source_checksum": ["def"],
        "subject_uuid": ["author1"],
        "title": ["Author Name"],
        "alias": ["author_alias"],
        "summary": ["Profile summary"],
        "avatar_url": ["http://example.com/avatar.png"],
        "interests": [["interest1"]],
    }
    con.insert("profiles", ibis.memtable(profiles_data, schema=PROFILES_SCHEMA))

    journals_data = {
        "id": ["journal1"],
        "content": ["Journal content"],
        "created_at": [datetime(2023, 1, 3, 12, 0, 0, tzinfo=timezone.utc)],
        "source_checksum": ["ghi"],
        "title": ["Journal Title"],
        "window_start": [datetime(2023, 1, 3, 0, 0, 0, tzinfo=timezone.utc)],
        "window_end": [datetime(2023, 1, 3, 23, 59, 59, tzinfo=timezone.utc)],
    }
    con.insert("journals", ibis.memtable(journals_data, schema=JOURNALS_SCHEMA))

    media_data = {
        "id": ["media1"],
        "content": ["Media description"],
        "created_at": [datetime(2023, 1, 4, 12, 0, 0, tzinfo=timezone.utc)],
        "source_checksum": ["jkl"],
        "filename": ["image.jpg"],
        "mime_type": ["image/jpeg"],
        "media_type": ["image"],
        "phash": ["123"],
    }
    con.insert("media", ibis.memtable(media_data, schema=MEDIA_SCHEMA))

    return con


def test_migrate_to_unified_schema_from_v2(v2_db_conn):
    """Tests migrating a V2 database to the unified schema."""
    # Run the migration
    migrate_to_unified_schema(v2_db_conn)

    # 1. Check if 'documents' table exists
    assert "documents" in v2_db_conn.list_tables()
    docs = v2_db_conn.table("documents")
    assert docs.count().execute() == 4

    # 2. Verify posts migration
    post_doc_df = docs.filter(_.doc_type == "post").execute()
    assert len(post_doc_df) == 1
    post_doc = post_doc_df.to_dict("records")[0]
    assert post_doc["id"] == "post1"
    assert post_doc["title"] == "Post Title"
    assert post_doc["published"].to_pydatetime().date() == date(2023, 1, 1)
    assert post_doc["authors"] == ["author1"]

    # 3. Verify profiles migration
    profile_doc_df = docs.filter(_.doc_type == "profile").execute()
    assert len(profile_doc_df) == 1
    profile_doc = profile_doc_df.to_dict("records")[0]
    assert profile_doc["id"] == "profile1"
    assert profile_doc["title"] == "Author Name"
    assert profile_doc["summary"] == "Profile summary"
    assert profile_doc["internal_metadata"]["alias"] == "author_alias"

    # 4. Verify journals migration
    journal_doc_df = docs.filter(_.doc_type == "journal").execute()
    assert len(journal_doc_df) == 1
    journal_doc = journal_doc_df.to_dict("records")[0]
    assert journal_doc["id"] == "journal1"
    assert journal_doc["title"] == "Journal Title"
    assert journal_doc["updated"].to_pydatetime() == datetime(2023, 1, 3, 12, 0, 0, tzinfo=timezone.utc)

    # 5. Verify media migration
    media_doc_df = docs.filter(_.doc_type == "media").execute()
    assert len(media_doc_df) == 1
    media_doc = media_doc_df.to_dict("records")[0]
    assert media_doc["id"] == "media1"
    assert media_doc["title"] == "image.jpg"
    assert media_doc["content_type"] == "image/jpeg"


@pytest.fixture
def partial_v3_db_conn():
    """Provides an in-memory DB with a partial 'documents' table."""
    con = ibis.duckdb.connect(":memory:")
    # Create a table with a subset of the final schema
    partial_schema = ibis.schema({"id": "string", "title": "string", "updated": "timestamp"})
    create_table_if_not_exists(con, "documents", partial_schema)
    return con


def test_migrate_documents_table_adds_missing_columns(partial_v3_db_conn):
    """Tests that migrate_documents_table adds missing columns."""
    con = partial_v3_db_conn
    migrate_documents_table(con)

    docs = con.table("documents")
    final_columns = {c.lower() for c in docs.columns}

    # Check that a few key columns were added
    assert "doc_type" in final_columns
    assert "published" in final_columns
    assert "internal_metadata" in final_columns

    # Check against the full schema
    from egregora.database.schemas import UNIFIED_SCHEMA

    target_columns = {c.lower() for c in UNIFIED_SCHEMA.names}
    assert final_columns == target_columns


def test_migrate_to_unified_schema_is_idempotent(v2_db_conn):
    """Tests that migrate_to_unified_schema can be run multiple times."""
    migrate_to_unified_schema(v2_db_conn)
    docs = v2_db_conn.table("documents")
    count_after_first_run = docs.count().execute()
    assert count_after_first_run == 4

    # Run a second time
    migrate_to_unified_schema(v2_db_conn)
    count_after_second_run = docs.count().execute()
    assert count_after_second_run == count_after_first_run


def test_migrate_documents_table_is_idempotent(partial_v3_db_conn):
    """Tests that migrate_documents_table can be run multiple times."""
    con = partial_v3_db_conn
    migrate_documents_table(con)
    table_after_first_run = con.table("documents")
    columns_after_first_run = table_after_first_run.columns

    # Run a second time
    migrate_documents_table(con)
    table_after_second_run = con.table("documents")
    columns_after_second_run = table_after_second_run.columns

    assert columns_after_first_run == columns_after_second_run
