"""Tests for author profile exceptions."""

import pytest

from egregora.knowledge.exceptions import (
    InvalidAliasError,
    ProfileNotFoundError,
    ProfileParseError,
)


def test_profile_not_found_error_with_uuid():
    """Test that ProfileNotFoundError sets author_uuid correctly."""
    author_uuid = "test-uuid"
    with pytest.raises(ProfileNotFoundError) as excinfo:
        raise ProfileNotFoundError("Profile not found", author_uuid=author_uuid)
    assert excinfo.value.author_uuid == author_uuid
    assert excinfo.value.path is None


def test_profile_not_found_error_with_path():
    """Test that ProfileNotFoundError sets path correctly."""
    path = "/test/path"
    with pytest.raises(ProfileNotFoundError) as excinfo:
        raise ProfileNotFoundError("Profile not found", path=path)
    assert excinfo.value.path == path
    assert excinfo.value.author_uuid is None


def test_profile_parse_error():
    """Test that ProfileParseError sets path correctly."""
    path = "/test/path"
    with pytest.raises(ProfileParseError) as excinfo:
        raise ProfileParseError("Parse error", path=path)
    assert excinfo.value.path == path


def test_invalid_alias_error():
    """Test that InvalidAliasError sets alias correctly."""
    alias = "test-alias"
    with pytest.raises(InvalidAliasError) as excinfo:
        raise InvalidAliasError("Invalid alias", alias=alias)
    assert excinfo.value.alias == alias
