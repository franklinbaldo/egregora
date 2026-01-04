"""Unit tests for database.profile_cache."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, PropertyMock

import pytest
from ibis.common.exceptions import IbisError

from egregora.database import schemas
from egregora.database.profile_cache import (
    get_all_profiles_from_db,
    get_opted_out_authors_from_db,
    get_profile_from_db,
    get_profile_posts_from_db,
    scan_and_cache_all_documents,
    scan_and_cache_posts,
    scan_and_cache_profiles,
)

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager


@pytest.fixture
def mock_storage() -> MagicMock:
    """Fixture to create a mock DuckDBStorageManager."""
    mock = MagicMock()
    mock.ibis_conn = MagicMock()
    return mock


def test_scan_and_cache_profiles_success(
    mock_storage: DuckDBStorageManager, tmp_path: Path, monkeypatch
):
    """Test successful scanning and caching of profiles."""
    mock_create_table = MagicMock()
    monkeypatch.setattr(schemas, "create_table_if_not_exists", mock_create_table)

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    profile_content = """---
uuid: "1234-5678"
alias: "Test User"
bio: "A test bio."
---
Profile content.
"""
    profile_file = profiles_dir / "1234-5678" / "index.md"
    profile_file.parent.mkdir()
    profile_file.write_text(profile_content, encoding="utf-8")

    cached_count = scan_and_cache_profiles(mock_storage, profiles_dir)

    assert cached_count == 1
    mock_create_table.assert_called_once_with(
        mock_storage._conn, "profiles", schemas.PROFILES_SCHEMA, overwrite=False
    )
    mock_storage.replace_rows.assert_called_once()
    mock_storage.ibis_conn.memtable.assert_called_once()

    memtable_arg = mock_storage.ibis_conn.memtable.call_args[0][0]
    assert len(memtable_arg) == 1
    row = memtable_arg[0]
    assert row["id"] == "1234-5678"
    assert row["alias"] == "Test User"

    replace_rows_kwargs = mock_storage.replace_rows.call_args.kwargs
    assert replace_rows_kwargs["by_keys"] == {"id": "1234-5678"}


def test_get_profile_from_db_found(mock_storage: DuckDBStorageManager):
    """Test get_profile_from_db when profile is found."""
    mock_table = MagicMock()
    mock_filtered_table = MagicMock()
    mock_storage.read_table.return_value = mock_table
    mock_table.filter.return_value = mock_filtered_table

    mock_df = MagicMock()
    mock_df.__len__.return_value = 1
    type(mock_df).iloc = PropertyMock(return_value=[{"content": "profile content"}])
    mock_filtered_table.execute.return_value = mock_df

    content = get_profile_from_db(mock_storage, "1234-5678")

    assert content == "profile content"
    mock_storage.read_table.assert_called_with("profiles")
    mock_table.filter.assert_called_once()


def test_get_profile_from_db_not_found(mock_storage: DuckDBStorageManager):
    """Test get_profile_from_db when profile is not found."""
    mock_table = MagicMock()
    mock_filtered_table = MagicMock()
    mock_storage.read_table.return_value = mock_table
    mock_table.filter.return_value = mock_filtered_table

    mock_df = MagicMock()
    mock_df.__len__.return_value = 0
    mock_filtered_table.execute.return_value = mock_df

    content = get_profile_from_db(mock_storage, "1234-5678")

    assert content == ""


def test_get_profile_from_db_error(mock_storage: DuckDBStorageManager):
    """Test get_profile_from_db when a database error occurs."""
    mock_storage.read_table.side_effect = IbisError("DB error")

    content = get_profile_from_db(mock_storage, "1234-5678")

    assert content == ""


def test_get_all_profiles_from_db(mock_storage: DuckDBStorageManager):
    """Test get_all_profiles_from_db."""
    mock_table = MagicMock()
    mock_storage.read_table.return_value = mock_table
    mock_df = MagicMock()
    mock_df.iterrows.return_value = iter(
        [
            (0, {"subject_uuid": "111", "content": "content 1"}),
            (1, {"subject_uuid": "222", "content": "content 2"}),
        ]
    )
    mock_table.execute.return_value = mock_df
    profiles = get_all_profiles_from_db(mock_storage)

    assert profiles == {"111": "content 1", "222": "content 2"}


def test_get_opted_out_authors_from_db(mock_storage: DuckDBStorageManager):
    """Test get_opted_out_authors_from_db."""
    mock_table = MagicMock()
    mock_storage.read_table.return_value = mock_table
    mock_df = MagicMock()
    mock_df.iterrows.return_value = iter(
        [
            (0, {"subject_uuid": "111", "content": "some content"}),
            (1, {"subject_uuid": "222", "content": "opt-out: true"}),
            (2, {"subject_uuid": "333", "content": "opted_out: true"}),
        ]
    )
    mock_table.execute.return_value = mock_df

    opted_out = get_opted_out_authors_from_db(mock_storage)

    assert opted_out == {"222", "333"}


def test_scan_and_cache_posts(
    mock_storage: DuckDBStorageManager, tmp_path: Path, monkeypatch
):
    """Test successful scanning and caching of posts."""
    mock_create_table = MagicMock()
    monkeypatch.setattr(schemas, "create_table_if_not_exists", mock_create_table)

    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()

    post_content = """---
title: "Test Post"
authors: ["1234-5678"]
---
Post body.
"""
    (posts_dir / "test-post.md").write_text(post_content, encoding="utf-8")

    cached_count = scan_and_cache_posts(mock_storage, posts_dir)

    assert cached_count == 1
    mock_create_table.assert_called_once_with(
        mock_storage._conn, "posts", schemas.POSTS_SCHEMA, overwrite=False
    )
    mock_storage.replace_rows.assert_called_once()
    row = mock_storage.ibis_conn.memtable.call_args[0][0][0]
    assert row["id"] == "test-post"
    assert row["authors"] == ["1234-5678"]


def test_get_profile_posts_from_db(mock_storage: DuckDBStorageManager):
    """Test get_profile_posts_from_db."""
    mock_table = MagicMock()
    mock_filtered_table = MagicMock()
    mock_storage.read_table.return_value = mock_table
    mock_table.filter.return_value = mock_filtered_table
    mock_df = MagicMock()
    mock_df.iterrows.return_value = iter(
        [
            (
                0,
                {
                    "slug": "post1",
                    "title": "Post 1",
                    "content": "content 1",
                    "date": "2023-01-01",
                    "summary": "sum 1",
                },
            ),
        ]
    )
    mock_filtered_table.execute.return_value = mock_df

    posts = get_profile_posts_from_db(mock_storage, "1234-5678")

    assert len(posts) == 1
    assert posts[0]["slug"] == "post1"


def test_scan_and_cache_all_documents(monkeypatch):
    """Test scan_and_cache_all_documents."""
    mock_scan_profiles = MagicMock(return_value=5)
    mock_scan_posts = MagicMock(return_value=10)
    monkeypatch.setattr(
        "egregora.database.profile_cache.scan_and_cache_profiles",
        mock_scan_profiles,
    )
    monkeypatch.setattr(
        "egregora.database.profile_cache.scan_and_cache_posts",
        mock_scan_posts,
    )

    mock_storage = MagicMock()
    profiles_dir = Path("p")
    posts_dir = Path("po")

    counts = scan_and_cache_all_documents(mock_storage, profiles_dir, posts_dir)

    assert counts == {"profiles": 5, "posts": 10}
    mock_scan_profiles.assert_called_once_with(mock_storage, profiles_dir)
    mock_scan_posts.assert_called_once_with(mock_storage, posts_dir)
