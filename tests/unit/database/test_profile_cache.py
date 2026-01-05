
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
from ibis import memtable

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
def mock_storage_manager():
    """Fixture for a mocked DuckDBStorageManager."""
    return MagicMock()

def test_scan_and_cache_profiles(mock_storage_manager, tmp_path: Path):
    """Test scanning and caching of profiles."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "367f0f63-b8a7-5a81-bf8e-3a3d22297e28.md").write_text("---\nuuid: 367f0f63-b8a7-5a81-bf8e-3a3d22297e28\nalias: User One\n---\n\nBio for User One.")
    (profiles_dir / "367f0f63-b8a7-5a81-bf8e-3a3d22297e29.md").write_text("---\nuuid: 367f0f63-b8a7-5a81-bf8e-3a3d22297e29\nalias: User Two\nopt-out: true\n---\n\nBio for User Two.")
    (profiles_dir / "not-a-profile.txt").write_text("This is not a profile.")

    count = scan_and_cache_profiles(mock_storage_manager, profiles_dir)

    assert count == 2
    assert mock_storage_manager.replace_rows.call_count == 2

def test_get_profile_from_db(mock_storage_manager):
    """Test retrieving a single profile from the database."""
    mock_table = memtable({"content": ["---\nuuid: user1\n---\n\nBio"], "subject_uuid": ["user1"]})
    mock_storage_manager.read_table.return_value.filter.return_value.execute.return_value = mock_table.execute()

    content = get_profile_from_db(mock_storage_manager, "user1")

    assert content == "---\nuuid: user1\n---\n\nBio"

def test_get_all_profiles_from_db(mock_storage_manager):
    """Test retrieving all profiles from the database."""
    mock_table = memtable(
        {
            "content": ["---\nuuid: user1\n---\n\nBio1", "---\nuuid: user2\n---\n\nBio2"],
            "subject_uuid": ["user1", "user2"],
        }
    )
    mock_storage_manager.read_table.return_value.execute.return_value = mock_table.execute()

    profiles = get_all_profiles_from_db(mock_storage_manager)

    assert len(profiles) == 2
    assert profiles["user1"] == "---\nuuid: user1\n---\n\nBio1"

def test_get_opted_out_authors_from_db(mock_storage_manager):
    """Test retrieving opted-out authors from the database."""
    mock_table = memtable(
        {
            "content": ["---\nopt-out: true\n---", "---\nopt-out: false\n---", "no frontmatter"],
            "subject_uuid": ["user1", "user2", "user3"],
        }
    )
    mock_storage_manager.read_table.return_value.execute.return_value = mock_table.execute()

    opted_out = get_opted_out_authors_from_db(mock_storage_manager)

    assert opted_out == {"user1"}

def test_scan_and_cache_posts(mock_storage_manager, tmp_path: Path):
    """Test scanning and caching of posts."""
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    (posts_dir / "post1.md").write_text("---\nslug: post1\nauthors: [user1]\n---\n\nContent 1.")
    (posts_dir / "post2.md").write_text("---\nslug: post2\nauthors: [user2]\n---\n\nContent 2.")

    count = scan_and_cache_posts(mock_storage_manager, posts_dir)

    assert count == 2
    assert mock_storage_manager.replace_rows.call_count == 2

def test_get_profile_posts_from_db(mock_storage_manager):
    """Test retrieving profile posts from the database."""
    mock_table = memtable(
        {
            "slug": ["post1"],
            "title": ["Post 1"],
            "content": ["Content 1"],
            "date": ["2025-01-01"],
            "summary": ["Summary 1"],
        }
    )
    mock_storage_manager.read_table.return_value.filter.return_value.execute.return_value = mock_table.execute()

    posts = get_profile_posts_from_db(mock_storage_manager, "user1")

    assert len(posts) == 1
    assert posts[0]["slug"] == "post1"

def test_scan_and_cache_all_documents(mock_storage_manager, tmp_path: Path):
    """Test scanning and caching all document types."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "367f0f63-b8a7-5a81-bf8e-3a3d22297e28.md").write_text("---\nuuid: 367f0f63-b8a7-5a81-bf8e-3a3d22297e28\n---\n\nBio.")

    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    (posts_dir / "post1.md").write_text("---\nslug: post1\n---\n\nContent.")

    counts = scan_and_cache_all_documents(mock_storage_manager, profiles_dir, posts_dir)

    assert counts["profiles"] == 1
    assert counts["posts"] == 1
    assert mock_storage_manager.replace_rows.call_count == 2
