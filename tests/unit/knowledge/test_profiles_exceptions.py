"""Tests for author profile exceptions."""

import uuid
from pathlib import Path

import pytest

from egregora.knowledge import profiles
from egregora.knowledge.exceptions import (
    InvalidAliasError,
    ProfileNotFoundError,
    ProfileParseError,
)


def test_profile_not_found_error_with_uuid():
    """Test that ProfileNotFoundError sets author_uuid correctly."""
    author_uuid = "test-uuid"
    with pytest.raises(ProfileNotFoundError) as excinfo:
        msg = "Profile not found"
        raise ProfileNotFoundError(msg, author_uuid=author_uuid)
    assert excinfo.value.author_uuid == author_uuid
    assert excinfo.value.path is None


def test_profile_not_found_error_with_path():
    """Test that ProfileNotFoundError sets path correctly."""
    path = "/test/path"
    with pytest.raises(ProfileNotFoundError) as excinfo:
        msg = "Profile not found"
        raise ProfileNotFoundError(msg, path=path)
    assert excinfo.value.path == path
    assert excinfo.value.author_uuid is None


def test_profile_parse_error():
    """Test that ProfileParseError sets path correctly."""
    path = "/test/path"
    with pytest.raises(ProfileParseError) as excinfo:
        msg = "Parse error"
        raise ProfileParseError(msg, path=path)
    assert excinfo.value.path == path


def test_invalid_alias_error():
    """Test that InvalidAliasError sets alias correctly."""
    alias = "test-alias"
    with pytest.raises(InvalidAliasError) as excinfo:
        msg = "Invalid alias"
        raise InvalidAliasError(msg, alias=alias)
    assert excinfo.value.alias == alias


# --- Test _find_profile_path ---


def test_find_profile_path_not_found(tmp_path):
    """Should raise ProfileNotFoundError if no profile can be found."""
    test_uuid = str(uuid.uuid4())
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    with pytest.raises(ProfileNotFoundError):
        profiles._find_profile_path(test_uuid, profiles_dir)


def test_find_profile_path_profiles_dir_not_found():
    """Should raise ProfileNotFoundError if the profiles directory does not exist."""
    test_uuid = str(uuid.uuid4())
    profiles_dir = Path("non/existent/dir")
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


def test_validate_alias_whitespace():
    """Should raise InvalidAliasError for an alias containing only whitespace."""
    with pytest.raises(InvalidAliasError):
        profiles._validate_alias("   ")


def test_validate_alias_with_control_chars():
    """Should raise InvalidAliasError for an alias with control characters."""
    with pytest.raises(InvalidAliasError):
        profiles._validate_alias("alias\x08with\x07control\x0bchars")
