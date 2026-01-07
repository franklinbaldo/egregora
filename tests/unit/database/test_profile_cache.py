from __future__ import annotations

import uuid
from pathlib import Path

import ibis
import pytest
from ibis import memtable

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
def storage_manager() -> DuckDBStorageManager:
    """Fixture for an in-memory DuckDBStorageManager."""
    backend = ibis.connect("duckdb://:memory:")
    return DuckDBStorageManager.from_ibis_backend(backend)


def test_scan_and_cache_profiles_e2e(storage_manager: DuckDBStorageManager, tmp_path: Path):
    """Test scanning and caching of profiles with an in-memory database."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())

    (profiles_dir / f"{uuid1}.md").write_text(
        f"---\nuuid: {uuid1}\nalias: User One\n---\n\nBio for User One."
    )
    (profiles_dir / uuid2).mkdir()
    (profiles_dir / uuid2 / "index.md").write_text(
        f"---\nuuid: {uuid2}\nalias: User Two\nopt-out: true\n---\n\nBio for User Two."
    )
    (profiles_dir / "not-a-profile.txt").write_text("This is not a profile.")

    count = scan_and_cache_profiles(storage_manager, profiles_dir)

    assert count == 2

    profiles_table = storage_manager.read_table("profiles")
    profiles = profiles_table.execute().to_dict("records")

    assert len(profiles) == 2
    profile1 = next(p for p in profiles if p["id"] == uuid1)
    assert profile1["alias"] == "User One"

    profile2 = next(p for p in profiles if p["id"] == uuid2)
    assert "opt-out: true" in profile2["content"]


def test_scan_and_cache_profiles_no_directory(storage_manager: DuckDBStorageManager, tmp_path: Path):
    """Test that caching handles a non-existent profiles directory gracefully."""
    profiles_dir = tmp_path / "non_existent_profiles"
    count = scan_and_cache_profiles(storage_manager, profiles_dir)
    assert count == 0


def test_get_profile_from_db_e2e(storage_manager: DuckDBStorageManager):
    """Test retrieving a single profile from the in-memory database."""
    schemas.create_table_if_not_exists(storage_manager._conn, "profiles", schemas.PROFILES_SCHEMA)
    profile_data = [
        {
            "id": "user1",
            "content": "---\nuuid: user1\n---\n\nBio",
            "subject_uuid": "user1",
            "title": "User One",
        }
    ]
    storage_manager.write_table(name="profiles", table=memtable(profile_data))

    content = get_profile_from_db(storage_manager, "user1")
    assert content == "---\nuuid: user1\n---\n\nBio"

    content_not_found = get_profile_from_db(storage_manager, "user_not_exist")
    assert content_not_found == ""


def test_get_all_profiles_from_db_e2e(storage_manager: DuckDBStorageManager):
    """Test retrieving all profiles from the in-memory database."""
    schemas.create_table_if_not_exists(storage_manager._conn, "profiles", schemas.PROFILES_SCHEMA)
    profile_data = [
        {"id": "user1", "content": "content1", "subject_uuid": "user1", "title": "User One"},
        {"id": "user2", "content": "content2", "subject_uuid": "user2", "title": "User Two"},
    ]
    storage_manager.write_table(name="profiles", table=memtable(profile_data))

    profiles = get_all_profiles_from_db(storage_manager)

    assert len(profiles) == 2
    assert profiles["user1"] == "content1"
    assert profiles["user2"] == "content2"


def test_get_opted_out_authors_from_db_e2e(storage_manager: DuckDBStorageManager):
    """Test retrieving opted-out authors from the in-memory database."""
    schemas.create_table_if_not_exists(storage_manager._conn, "profiles", schemas.PROFILES_SCHEMA)
    profile_data = [
        {"id": "user1", "content": "---\nopt-out: true\n---", "subject_uuid": "user1", "title": "User One"},
        {"id": "user2", "content": "---\nopted_out: true\n---", "subject_uuid": "user2", "title": "User Two"},
        {"id": "user3", "content": "no frontmatter", "subject_uuid": "user3", "title": "User Three"},
    ]
    storage_manager.write_table(name="profiles", table=memtable(profile_data))

    opted_out = get_opted_out_authors_from_db(storage_manager)
    assert opted_out == {"user1", "user2"}


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

    posts_table = storage_manager.read_table("posts")
    posts = posts_table.execute().to_dict("records")
    assert len(posts) == 2

    post1 = next(p for p in posts if p["slug"] == "post1")
    assert author_uuid in post1["authors"]

    post2 = next(p for p in posts if p["slug"] == "post2")
    assert author_uuid in post2["authors"]


def test_get_profile_posts_from_db_e2e(storage_manager: DuckDBStorageManager):
    """Test retrieving profile posts from the in-memory database."""
    schemas.create_table_if_not_exists(storage_manager._conn, "posts", schemas.POSTS_SCHEMA)
    post_data = [
        {
            "id": "post1",
            "slug": "post1",
            "title": "Post 1",
            "content": "Content 1",
            "date": "2025-01-01",
            "summary": "Summary 1",
            "authors": ["user1"],
        },
        {
            "id": "post2",
            "slug": "post2",
            "title": "Post 2",
            "content": "Content 2",
            "date": "2025-01-02",
            "summary": "Summary 2",
            "authors": ["user1", "user2"],
        },
        {
            "id": "post3",
            "slug": "post3",
            "title": "Post 3",
            "content": "Content 3",
            "date": "2025-01-03",
            "summary": "Summary 3",
            "authors": ["user2"],
        },
    ]
    storage_manager.write_table(name="posts", table=memtable(post_data))

    posts_user1 = get_profile_posts_from_db(storage_manager, "user1")
    assert len(posts_user1) == 2
    assert {p["slug"] for p in posts_user1} == {"post1", "post2"}

    posts_user2 = get_profile_posts_from_db(storage_manager, "user2")
    assert len(posts_user2) == 2
    assert {p["slug"] for p in posts_user2} == {"post2", "post3"}

    posts_user3 = get_profile_posts_from_db(storage_manager, "user3")
    assert len(posts_user3) == 0


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

    assert storage_manager.table_exists("profiles")
    assert storage_manager.read_table("profiles").count().execute() == 1
    assert storage_manager.table_exists("posts")
    assert storage_manager.read_table("posts").count().execute() == 1

from unittest.mock import patch

def test_get_profile_from_db_exception(storage_manager: DuckDBStorageManager):
    """Test exception handling in get_profile_from_db."""
    # Mock read_table to raise Exception
    with patch.object(storage_manager, 'read_table', side_effect=Exception("DB Error")):
        result = get_profile_from_db(storage_manager, "user1")
        assert result == ""

def test_get_all_profiles_from_db_exception(storage_manager: DuckDBStorageManager):
    """Test exception handling in get_all_profiles_from_db."""
    with patch.object(storage_manager, 'read_table', side_effect=Exception("DB Error")):
        result = get_all_profiles_from_db(storage_manager)
        assert result == {}

def test_get_opted_out_authors_from_db_exception(storage_manager: DuckDBStorageManager):
    """Test exception handling in get_opted_out_authors_from_db."""
    with patch.object(storage_manager, 'read_table', side_effect=Exception("DB Error")):
        result = get_opted_out_authors_from_db(storage_manager)
        assert result == set()

def test_get_profile_posts_from_db_exception(storage_manager: DuckDBStorageManager):
    """Test exception handling in get_profile_posts_from_db."""
    with patch.object(storage_manager, 'read_table', side_effect=Exception("DB Error")):
        result = get_profile_posts_from_db(storage_manager, "user1")
        assert result == []
