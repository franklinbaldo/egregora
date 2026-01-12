"""Unit tests for the profile knowledge module."""

import uuid

import pytest

from egregora.knowledge import profiles
from egregora.knowledge.exceptions import ProfileNotFoundError


def test_get_uuid_from_profile_success_from_frontmatter(tmp_path):
    """Should successfully extract UUID from YAML frontmatter."""
    profile_path = tmp_path / "profile.md"
    test_uuid = str(uuid.uuid4())
    profile_path.write_text(f"---\nuuid: {test_uuid}\n---")
    assert profiles._get_uuid_from_profile(profile_path) == test_uuid


def test_get_uuid_from_profile_success_from_subject(tmp_path):
    """Should successfully extract UUID from subject frontmatter."""
    profile_path = tmp_path / "profile.md"
    test_uuid = str(uuid.uuid4())
    profile_path.write_text(f"---\nsubject: {test_uuid}\n---")
    assert profiles._get_uuid_from_profile(profile_path) == test_uuid


def test_get_uuid_from_profile_success_from_legacy_filename(tmp_path):
    """Should successfully extract UUID from a legacy filename."""
    test_uuid = str(uuid.uuid4())
    profile_path = tmp_path / f"{test_uuid}.md"
    profile_path.write_text("no frontmatter")
    assert profiles._get_uuid_from_profile(profile_path) == test_uuid


def test_read_profile_reads_existing_profile(tmp_path):
    """Should correctly read an existing profile."""
    author_uuid = str(uuid.uuid4())
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile_path = profiles_dir / f"{author_uuid}.md"
    profile_content = f"---\nsubject: {author_uuid}\n---\n\nBio content."
    profile_path.write_text(profile_content, encoding="utf-8")
    # For this test, we care about the content, not the metadata parsing.
    # The function is expected to return the raw content of the profile file.
    assert profiles.read_profile(author_uuid, profiles_dir) == profile_content


def test_read_profile_should_raise_not_found_for_missing_profile(tmp_path):
    """Should raise ProfileNotFoundError for a missing profile (desired behavior)."""
    non_existent_uuid = str(uuid.uuid4())
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    with pytest.raises(ProfileNotFoundError):
        profiles.read_profile(non_existent_uuid, profiles_dir)
