"""Tests for document caching (profile_cache.py)."""

import uuid
from pathlib import Path

import pytest

from egregora.data_primitives.document import DocumentType
from egregora.database import schemas
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.profile_cache import (
    get_all_profiles_from_db,
    get_opted_out_authors_from_db,
    get_profile_from_db,
    get_profile_posts_from_db,
    scan_and_cache_all_documents,
    scan_and_cache_posts,
    scan_and_cache_profiles,
)


@pytest.fixture
def storage_manager():
    """Fixture for in-memory storage manager."""
    return DuckDBStorageManager(db_path=None)


def test_scan_and_cache_profiles_e2e(storage_manager: DuckDBStorageManager, tmp_path: Path):
    """Test scanning and caching of profiles with an in-memory database."""
    # Create temp profile files
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    # Profile 1: output/profiles/{uuid}.md
    uuid1 = str(uuid.uuid4())
    (profiles_dir / f"{uuid1}.md").write_text("---\nname: Test User\n---\n\nBio content.")

    # Profile 2: output/profiles/{uuid}/index.md
    uuid2 = str(uuid.uuid4())
    (profiles_dir / uuid2).mkdir()
    (profiles_dir / uuid2 / "index.md").write_text("---\nname: Test User 2\n---\n\nBio content 2.")

    # Run scan
    count = scan_and_cache_profiles(storage_manager, profiles_dir)

    assert count == 2

    # Verify data in DB
    # Now it should be in 'documents' table with doc_type='profile'
    table = storage_manager.read_table("documents")
    result = table.filter(table.doc_type == DocumentType.PROFILE.value).execute()
    assert len(result) == 2

    # Verify content
    row1 = result[result.id == uuid1].iloc[0]
    assert "Bio content." in row1["content"]
    assert row1["subject_uuid"] == uuid1


def test_scan_and_cache_profiles_no_directory(storage_manager: DuckDBStorageManager, tmp_path: Path):
    """Test behavior when profiles directory doesn't exist."""
    non_existent = tmp_path / "non_existent"
    count = scan_and_cache_profiles(storage_manager, non_existent)
    assert count == 0


def test_get_profile_from_db_e2e(storage_manager: DuckDBStorageManager):
    """Test retrieving a single profile from the in-memory database."""
    # Ensure documents table exists
    schemas.create_table_if_not_exists(storage_manager._conn, "documents", schemas.UNIFIED_SCHEMA)

    author_uuid = str(uuid.uuid4())
    content = "Some markdown content"

    # Insert manually
    storage_manager._conn.execute(
        "INSERT INTO documents (id, doc_type, status, content, subject_uuid, created_at, source_checksum) VALUES (?, ?, 'published', ?, ?, CURRENT_TIMESTAMP, 'hash')",
        (author_uuid, DocumentType.PROFILE.value, content, author_uuid),
    )

    # Retrieve
    result = get_profile_from_db(storage_manager, author_uuid)
    assert result == content

    # Retrieve non-existent
    assert get_profile_from_db(storage_manager, str(uuid.uuid4())) == ""


def test_get_all_profiles_from_db_e2e(storage_manager: DuckDBStorageManager):
    """Test retrieving all profiles from the in-memory database."""
    # Ensure documents table exists
    schemas.create_table_if_not_exists(storage_manager._conn, "documents", schemas.UNIFIED_SCHEMA)

    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())

    storage_manager._conn.execute(
        "INSERT INTO documents (id, doc_type, status, content, subject_uuid, created_at, source_checksum) VALUES (?, ?, 'published', 'c1', ?, CURRENT_TIMESTAMP, 'hash1')",
        (uuid1, DocumentType.PROFILE.value, uuid1),
    )
    storage_manager._conn.execute(
        "INSERT INTO documents (id, doc_type, status, content, subject_uuid, created_at, source_checksum) VALUES (?, ?, 'published', 'c2', ?, CURRENT_TIMESTAMP, 'hash2')",
        (uuid2, DocumentType.PROFILE.value, uuid2),
    )

    profiles = get_all_profiles_from_db(storage_manager)
    assert len(profiles) == 2
    assert profiles[uuid1] == "c1"
    assert profiles[uuid2] == "c2"


def test_get_opted_out_authors_from_db_e2e(storage_manager: DuckDBStorageManager):
    """Test retrieving opted-out authors from the in-memory database."""
    # Ensure documents table exists
    schemas.create_table_if_not_exists(storage_manager._conn, "documents", schemas.UNIFIED_SCHEMA)

    uuid_opt_out = str(uuid.uuid4())
    uuid_normal = str(uuid.uuid4())

    storage_manager._conn.execute(
        "INSERT INTO documents (id, doc_type, status, content, subject_uuid, created_at, source_checksum) VALUES (?, ?, 'published', 'opt-out: true', ?, CURRENT_TIMESTAMP, 'hash_opt')",
        (uuid_opt_out, DocumentType.PROFILE.value, uuid_opt_out),
    )
    storage_manager._conn.execute(
        "INSERT INTO documents (id, doc_type, status, content, subject_uuid, created_at, source_checksum) VALUES (?, ?, 'published', 'normal bio', ?, CURRENT_TIMESTAMP, 'hash_norm')",
        (uuid_normal, DocumentType.PROFILE.value, uuid_normal),
    )

    opted_out = get_opted_out_authors_from_db(storage_manager)
    assert len(opted_out) == 1
    assert uuid_opt_out in opted_out


def test_scan_and_cache_posts_e2e(storage_manager: DuckDBStorageManager, tmp_path: Path):
    """Test scanning and caching of posts with an in-memory database."""
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    author_uuid = str(uuid.uuid4())
    (posts_dir / "post1.md").write_text(f"---\nslug: post1\nauthors: ['{author_uuid}']\n---\n\nContent 1.")
    (posts_dir / "profiles").mkdir()
    (posts_dir / "profiles" / author_uuid).mkdir()
    (posts_dir / "profiles" / author_uuid / "post2.md").write_text("---\nslug: post2\n---\n\nContent 2.")

    count = scan_and_cache_posts(storage_manager, posts_dir)

    assert count == 2

    table = storage_manager.read_table("documents")
    result = table.filter(table.doc_type == DocumentType.POST.value).execute()
    assert len(result) == 2

    # Verify post2 was linked to author
    post2 = result[result.id == "post2"].iloc[0]
    # authors is array of string, check if it contains author_uuid
    # Ibis array usually comes back as list or numpy array
    assert author_uuid in post2["authors"]


def test_get_profile_posts_from_db_e2e(storage_manager: DuckDBStorageManager):
    """Test retrieving profile posts from the in-memory database."""
    # Ensure documents table exists
    schemas.create_table_if_not_exists(storage_manager._conn, "documents", schemas.UNIFIED_SCHEMA)

    author_uuid = str(uuid.uuid4())
    other_uuid = str(uuid.uuid4())

    # Insert posts using raw SQL for array support
    storage_manager._conn.execute(
        f"""
        INSERT INTO documents (id, doc_type, status, content, slug, title, authors, created_at, source_checksum)
        VALUES
        ('p1', '{DocumentType.POST.value}', 'published', 'c1', 'p1', 't1', ARRAY['{author_uuid}'], CURRENT_TIMESTAMP, 'hash1'),
        ('p2', '{DocumentType.POST.value}', 'published', 'c2', 'p2', 't2', ARRAY['{other_uuid}'], CURRENT_TIMESTAMP, 'hash2')
        """
    )

    posts = get_profile_posts_from_db(storage_manager, author_uuid)
    assert len(posts) == 1
    assert posts[0]["slug"] == "p1"


def test_scan_and_cache_all_documents_e2e(storage_manager: DuckDBStorageManager, tmp_path: Path):
    """Test scanning and caching all document types with an in-memory database."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile_uuid = str(uuid.uuid4())
    (profiles_dir / f"{profile_uuid}.md").write_text(f"---\nuuid: {profile_uuid}\n---\n\nBio.")

    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    (posts_dir / "post1.md").write_text("---\nslug: post1\n---\n\nContent.")

    counts = scan_and_cache_all_documents(storage_manager, profiles_dir, posts_dir)

    assert counts["profiles"] == 1
    assert counts["posts"] == 1

    # Both should be in documents table
    table = storage_manager.read_table("documents")
    count = table.count().execute()
    assert count == 2
