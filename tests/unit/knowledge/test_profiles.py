"""Unit tests for the profile knowledge module."""

import uuid
from pathlib import Path

import pytest

from egregora.knowledge import profiles
from egregora.knowledge.exceptions import (
    InvalidAliasError,
    ProfileNotFoundError,
    ProfileParseError,
)

# --- Test _get_uuid_from_profile ---


def test_get_uuid_from_profile_not_found():
    """Should raise ProfileNotFoundError if the file does not exist."""
    non_existent_path = Path("non/existent/path.md")
    with pytest.raises(ProfileNotFoundError):
        profiles._get_uuid_from_profile(non_existent_path)


def test_get_uuid_from_profile_parse_error(tmp_path):
    """Should raise ProfileParseError for a malformed file."""
    profile_path = tmp_path / "profile.md"
    profile_path.write_text("this is not valid frontmatter")
    with pytest.raises(ProfileParseError):
        profiles._get_uuid_from_profile(profile_path)


def test_get_uuid_from_profile_success_from_frontmatter(tmp_path):
    """Should successfully extract UUID from YAML frontmatter."""
    profile_path = tmp_path / "profile.md"
    test_uuid = str(uuid.uuid4())
    profile_path.write_text(f"---\nuuid: {test_uuid}\n---")
    assert profiles._get_uuid_from_profile(profile_path) == test_uuid


def test_get_uuid_from_profile_success_from_legacy_filename(tmp_path):
    """Should successfully extract UUID from a legacy filename."""
    test_uuid = str(uuid.uuid4())
    profile_path = tmp_path / f"{test_uuid}.md"
    profile_path.write_text("no frontmatter")
    # The function now expects a UUID to be found, so we assert it.
    # An empty file without a UUID in the name would raise ProfileParseError.
    assert profiles._get_uuid_from_profile(profile_path) == test_uuid


def test_get_uuid_from_profile_parse_error_on_empty_file(tmp_path):
    """Should raise ProfileParseError if file is empty and filename is not a UUID."""
    profile_path = tmp_path / "profile.md"
    profile_path.write_text("")
    with pytest.raises(ProfileParseError):
        profiles._get_uuid_from_profile(profile_path)


# --- Test _find_profile_path ---


def test_find_profile_path_not_found(tmp_path):
    """Should raise ProfileNotFoundError if no profile can be found."""
    test_uuid = str(uuid.uuid4())
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    with pytest.raises(ProfileNotFoundError):
        profiles._find_profile_path(test_uuid, profiles_dir)


# --- Test _validate_alias ---


def test_validate_alias_too_long():
    """Should raise InvalidAliasError for an alias that is too long."""
    with pytest.raises(InvalidAliasError):
        profiles._validate_alias("a" * 41)


def test_validate_alias_empty():
    """Should raise InvalidAliasError for an empty alias."""
    with pytest.raises(InvalidAliasError):
        profiles._validate_alias("")


def test_validate_alias_with_control_chars():
    """Should raise InvalidAliasError for an alias with control characters."""
    with pytest.raises(InvalidAliasError):
        profiles._validate_alias("alias\x08with\x07control\x0bchars")
