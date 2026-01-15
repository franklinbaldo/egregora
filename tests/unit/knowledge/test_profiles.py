"""Unit tests for the profile knowledge module."""

import uuid

import pytest

from egregora.knowledge import profiles
from egregora.knowledge.exceptions import ProfileNotFoundError


def test_read_profile_should_raise_not_found_for_missing_profile(tmp_path):
    """Should raise ProfileNotFoundError for a missing profile (desired behavior)."""
    non_existent_uuid = str(uuid.uuid4())
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    with pytest.raises(ProfileNotFoundError):
        profiles.read_profile(non_existent_uuid, profiles_dir)


def test_sync_all_profiles_raises_keyerror_on_missing_uuid(tmp_path):
    """Should raise KeyError if a profile is missing a UUID in its metadata."""
    profiles_dir = tmp_path / "output" / "profiles"
    author_dir = profiles_dir / "test-author"
    author_dir.mkdir(parents=True)
    (author_dir / "index.md").write_text("---\nname: Test Author\n---\n\n# Hello", "utf-8")

    with pytest.raises(KeyError):
        profiles.sync_all_profiles(profiles_dir)
