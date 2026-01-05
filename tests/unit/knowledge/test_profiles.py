"""Unit tests for the profile knowledge module."""

import uuid

from egregora.knowledge import profiles


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
    # The function now expects a UUID to be found, so we assert it.
    # An empty file without a UUID in the name would raise ProfileParseError.
    assert profiles._get_uuid_from_profile(profile_path) == test_uuid
