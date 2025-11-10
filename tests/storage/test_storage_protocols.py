"""Contract tests for storage protocol implementations.

These tests verify that all storage implementations (MkDocs, in-memory, future database/S3)
correctly implement the storage protocol interfaces. Each implementation should pass all
contract tests to ensure consistent behavior.

Run these tests against all storage implementations:
- MkDocsPostStorage, MkDocsProfileStorage, MkDocsJournalStorage
- InMemoryPostStorage, InMemoryProfileStorage, InMemoryJournalStorage
- Future implementations (DatabaseStorage, S3Storage, etc.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from egregora.storage import JournalStorage, PostStorage, ProfileStorage
from egregora.storage.memory import InMemoryJournalStorage, InMemoryPostStorage, InMemoryProfileStorage
from egregora.rendering.mkdocs import MkDocsJournalStorage, MkDocsPostStorage, MkDocsProfileStorage

# --- Fixtures for all storage implementations ---


@pytest.fixture
def post_storages(tmp_path: Path) -> list[tuple[str, PostStorage]]:
    """Return all PostStorage implementations for contract testing."""
    return [
        ("InMemory", InMemoryPostStorage()),
        ("MkDocs", MkDocsPostStorage(tmp_path)),
    ]


@pytest.fixture
def profile_storages(tmp_path: Path) -> list[tuple[str, ProfileStorage]]:
    """Return all ProfileStorage implementations for contract testing."""
    return [
        ("InMemory", InMemoryProfileStorage()),
        ("MkDocs", MkDocsProfileStorage(tmp_path)),
    ]


@pytest.fixture
def journal_storages(tmp_path: Path) -> list[tuple[str, JournalStorage]]:
    """Return all JournalStorage implementations for contract testing."""
    return [
        ("InMemory", InMemoryJournalStorage()),
        ("MkDocs", MkDocsJournalStorage(tmp_path)),
    ]


# --- PostStorage contract tests ---


def test_post_storage_write_returns_identifier(post_storages):
    """Contract: write() must return a non-empty string identifier."""
    for impl_name, storage in post_storages:
        result = storage.write(
            slug="test-post",
            metadata={"title": "Test Post", "date": "2025-01-10"},
            content="# Test\n\nContent here.",
        )
        assert isinstance(result, str), f"{impl_name}: write() must return a string"
        assert len(result) > 0, f"{impl_name}: write() must return non-empty identifier"


def test_post_storage_read_nonexistent_returns_none(post_storages):
    """Contract: read() must return None for posts that don't exist."""
    for impl_name, storage in post_storages:
        result = storage.read("nonexistent-slug")
        assert result is None, f"{impl_name}: read() must return None for nonexistent posts"


def test_post_storage_write_then_read_roundtrip(post_storages):
    """Contract: write() followed by read() must return the same content."""
    for impl_name, storage in post_storages:
        metadata = {"title": "Roundtrip Test", "date": "2025-01-10", "draft": False}
        content = "# Roundtrip\n\nThis is a test."

        # Write
        post_id = storage.write(slug="roundtrip-test", metadata=metadata, content=content)
        assert post_id is not None, f"{impl_name}: write() returned None"

        # Read
        result = storage.read("roundtrip-test")
        assert result is not None, f"{impl_name}: read() returned None after write()"

        read_metadata, read_content = result
        assert read_metadata["title"] == metadata["title"], f"{impl_name}: metadata mismatch"
        assert read_content == content, f"{impl_name}: content mismatch"


def test_post_storage_exists_returns_bool(post_storages):
    """Contract: exists() must return a boolean."""
    for impl_name, storage in post_storages:
        # Before write
        assert storage.exists("test-exists") is False, f"{impl_name}: exists() should return False initially"

        # After write
        storage.write(slug="test-exists", metadata={"title": "Test"}, content="Content")
        assert storage.exists("test-exists") is True, (
            f"{impl_name}: exists() should return True after write()"
        )


def test_post_storage_write_overwrites_existing(post_storages):
    """Contract: write() must overwrite existing posts with the same slug."""
    for impl_name, storage in post_storages:
        # Write v1
        storage.write(slug="overwrite-test", metadata={"title": "Version 1"}, content="Content v1")

        # Write v2 (overwrite)
        storage.write(slug="overwrite-test", metadata={"title": "Version 2"}, content="Content v2")

        # Read should return v2
        result = storage.read("overwrite-test")
        assert result is not None, f"{impl_name}: read() returned None"
        metadata, content = result
        assert metadata["title"] == "Version 2", f"{impl_name}: write() did not overwrite existing post"
        assert content == "Content v2", f"{impl_name}: write() did not overwrite content"


# --- ProfileStorage contract tests ---


def test_profile_storage_write_returns_identifier(profile_storages):
    """Contract: write() must return a non-empty string identifier."""
    for impl_name, storage in profile_storages:
        result = storage.write(author_uuid="test-uuid-123", content="---\nalias: Test User\n---\n\nBio here.")
        assert isinstance(result, str), f"{impl_name}: write() must return a string"
        assert len(result) > 0, f"{impl_name}: write() must return non-empty identifier"


def test_profile_storage_read_nonexistent_returns_none(profile_storages):
    """Contract: read() must return None for profiles that don't exist."""
    for impl_name, storage in profile_storages:
        result = storage.read("nonexistent-uuid")
        assert result is None, f"{impl_name}: read() must return None for nonexistent profiles"


def test_profile_storage_write_then_read_roundtrip(profile_storages):
    """Contract: write() followed by read() must return the same content."""
    for impl_name, storage in profile_storages:
        content = "---\nalias: Alice\nbio: AI researcher\n---\n\nAlice's profile."

        # Write
        profile_id = storage.write(author_uuid="alice-uuid", content=content)
        assert profile_id is not None, f"{impl_name}: write() returned None"

        # Read
        read_content = storage.read("alice-uuid")
        assert read_content is not None, f"{impl_name}: read() returned None after write()"
        assert read_content == content, f"{impl_name}: content mismatch"


def test_profile_storage_exists_returns_bool(profile_storages):
    """Contract: exists() must return a boolean."""
    for impl_name, storage in profile_storages:
        # Before write
        assert storage.exists("test-uuid") is False, f"{impl_name}: exists() should return False initially"

        # After write
        storage.write(author_uuid="test-uuid", content="Profile content")
        assert storage.exists("test-uuid") is True, f"{impl_name}: exists() should return True after write()"


def test_profile_storage_write_overwrites_existing(profile_storages):
    """Contract: write() must overwrite existing profiles with the same UUID."""
    for impl_name, storage in profile_storages:
        # Write v1
        storage.write(author_uuid="overwrite-uuid", content="Profile v1")

        # Write v2 (overwrite)
        storage.write(author_uuid="overwrite-uuid", content="Profile v2")

        # Read should return v2
        content = storage.read("overwrite-uuid")
        assert content is not None, f"{impl_name}: read() returned None"
        assert content == "Profile v2", f"{impl_name}: write() did not overwrite existing profile"


# --- JournalStorage contract tests ---


def test_journal_storage_write_returns_identifier(journal_storages):
    """Contract: write() must return a non-empty string identifier."""
    for impl_name, storage in journal_storages:
        result = storage.write(window_label="2025-01-10 10:00 to 12:00", content="# Journal\n\nEntry here.")
        assert isinstance(result, str), f"{impl_name}: write() must return a string"
        assert len(result) > 0, f"{impl_name}: write() must return non-empty identifier"


def test_journal_storage_write_sanitizes_label(journal_storages):
    """Contract: write() must sanitize window labels for safe identifiers."""
    for impl_name, storage in journal_storages:
        # Labels with special characters (colons, spaces)
        result = storage.write(window_label="2025-01-10 10:00 to 12:00", content="Test")
        assert result is not None, f"{impl_name}: write() failed with special characters in label"

        # Identifier should not contain problematic characters
        # (Implementation-specific, but should be safe for filesystem/URLs)
        if impl_name == "MkDocs":
            # MkDocs uses filesystem, should replace : and spaces
            assert ":" not in result, f"{impl_name}: identifier contains colon"
        elif impl_name == "InMemory":
            # In-memory uses memory:// scheme, should sanitize label part
            assert "memory://journal/" in result, f"{impl_name}: identifier should have memory:// prefix"


def test_journal_storage_write_then_read_roundtrip(journal_storages):
    """Contract: write() followed by get_by_label() must return the same content."""
    for impl_name, storage in journal_storages:
        content = "---\nwindow_label: Test Window\n---\n\n# Journal Entry\n\nContent here."

        # Write
        journal_id = storage.write(window_label="Test Window", content=content)
        assert journal_id is not None, f"{impl_name}: write() returned None"

        # Read (using get_by_label if available)
        if hasattr(storage, "get_by_label"):
            read_content = storage.get_by_label("Test Window")
            assert read_content is not None, f"{impl_name}: get_by_label() returned None after write()"
            assert read_content == content, f"{impl_name}: content mismatch"


def test_journal_storage_write_overwrites_existing(journal_storages):
    """Contract: write() must overwrite existing journals with the same label."""
    for impl_name, storage in journal_storages:
        # Write v1
        storage.write(window_label="Overwrite Test", content="Journal v1")

        # Write v2 (overwrite)
        storage.write(window_label="Overwrite Test", content="Journal v2")

        # Read should return v2
        if hasattr(storage, "get_by_label"):
            content = storage.get_by_label("Overwrite Test")
            assert content is not None, f"{impl_name}: get_by_label() returned None"
            assert content == "Journal v2", f"{impl_name}: write() did not overwrite existing journal"


# --- Protocol validation tests ---


def test_post_storage_is_runtime_checkable(post_storages):
    """Contract: PostStorage must be runtime_checkable for isinstance() checks."""
    for impl_name, storage in post_storages:
        assert isinstance(storage, PostStorage), f"{impl_name}: not recognized as PostStorage instance"


def test_profile_storage_is_runtime_checkable(profile_storages):
    """Contract: ProfileStorage must be runtime_checkable for isinstance() checks."""
    for impl_name, storage in profile_storages:
        assert isinstance(storage, ProfileStorage), f"{impl_name}: not recognized as ProfileStorage instance"


def test_journal_storage_is_runtime_checkable(journal_storages):
    """Contract: JournalStorage must be runtime_checkable for isinstance() checks."""
    for impl_name, storage in journal_storages:
        assert isinstance(storage, JournalStorage), f"{impl_name}: not recognized as JournalStorage instance"
