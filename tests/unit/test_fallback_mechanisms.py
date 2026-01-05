from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ibis.common.exceptions import IbisError

from egregora.data_primitives.document import DocumentType
from egregora.knowledge.profiles import get_opted_out_authors
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter


@pytest.fixture
def mock_storage_manager_with_error():
    """Fixture for a mocked DuckDBStorageManager that raises an error."""
    mock_storage = MagicMock()
    mock_storage.read_table.side_effect = IbisError("Database connection failed")
    return mock_storage


def test_get_opted_out_authors_fallback(tmp_path: Path):
    """Test that get_opted_out_authors falls back to filesystem on DB error."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    # Opted-out user
    (profiles_dir / "user1").mkdir()
    (profiles_dir / "user1" / "index.md").write_text(
        "---\nuuid: user1\n---\n\nStatus: OPTED OUT"
    )

    # Opted-in user
    (profiles_dir / "user2").mkdir()
    (profiles_dir / "user2" / "index.md").write_text("---\nuuid: user2\n---\n\nStatus: Opted in")

    mock_storage = MagicMock()
    # Simulate DB error by patching the function that reads from the DB
    with patch(
        "egregora.knowledge.profiles.get_opted_out_authors_from_db",
        side_effect=IbisError("DB connection failed"),
    ) as mock_db_call:
        opted_out_authors = get_opted_out_authors(profiles_dir, storage=mock_storage)

        # Assert that the DB function was called, failed, and the code fell back
        mock_db_call.assert_called_once()
        assert opted_out_authors == {"user1"}


def test_mkdocs_adapter_get_profile_fallback(tmp_path: Path):
    """Test that MkDocsAdapter.get falls back to filesystem for profiles on DB error."""
    site_root = tmp_path
    (site_root / "mkdocs.yml").touch()
    docs_dir = site_root / "docs"
    docs_dir.mkdir()
    profiles_dir = docs_dir / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "user1").mkdir()
    (profiles_dir / "user1" / "index.md").write_text(
        "---\nuuid: user1\nalias: User One\n---\n\nProfile content."
    )

    adapter = MkDocsAdapter()

    # Simulate a DB error by patching the underlying DB call
    with patch(
        "egregora.database.profile_cache.get_profile_from_db",
        side_effect=IbisError("DB error"),
    ) as mock_db_call:
        # Initialize adapter with a mock storage
        mock_storage = MagicMock()
        adapter.initialize(site_root, storage=mock_storage)
        adapter.profiles_dir = profiles_dir

        # Call the get method
        document = adapter.get(DocumentType.PROFILE, "user1")

        # Verify fallback occurred
        mock_db_call.assert_called_once_with(mock_storage, "user1")
        assert document is not None
        assert document.metadata["alias"] == "User One"
        assert document.content.strip() == "Profile content."


def test_mkdocs_adapter_get_post_fallback(tmp_path: Path):
    """Test that MkDocsAdapter.get falls back to filesystem for posts on DB error."""
    site_root = tmp_path
    (site_root / "mkdocs.yml").touch()
    posts_dir = site_root / "docs" / "posts"
    posts_dir.mkdir(parents=True)
    (posts_dir / "2025-01-01-my-post.md").write_text(
        "---\nslug: my-post\ntitle: My Post\n---\n\nPost content."
    )

    adapter = MkDocsAdapter()
    mock_storage = MagicMock()
    # Simulate DB error by having the read_table call fail
    mock_storage.read_table.side_effect = IbisError("DB error")

    # Initialize adapter
    adapter.initialize(site_root, storage=mock_storage)

    # Call the get method
    document = adapter.get(DocumentType.POST, "my-post")

    # Verify fallback occurred
    mock_storage.read_table.assert_called_once_with("posts")
    assert document is not None
    assert document.metadata["title"] == "My Post"
    assert document.content.strip() == "Post content."
