"""Unit tests for the profiles module."""

from pathlib import Path

import pytest

from egregora.knowledge.exceptions import InvalidAliasError, ProfileNotFoundError, ProfileParsingError
from egregora.knowledge.profiles import _get_uuid_from_profile, _validate_alias, read_profile


def test_read_profile_not_found(tmp_path: Path):
    """Test that read_profile raises ProfileNotFoundError for a non-existent profile."""
    non_existent_uuid = "00000000-0000-0000-0000-000000000000"
    profiles_dir = tmp_path / "profiles"

    with pytest.raises(ProfileNotFoundError) as excinfo:
        read_profile(non_existent_uuid, profiles_dir)

    assert non_existent_uuid in str(excinfo.value)


def test_get_uuid_from_profile_parsing_error(tmp_path: Path):
    """Test that _get_uuid_from_profile raises ProfileParsingError for a malformed file."""
    malformed_profile = tmp_path / "malformed.md"
    malformed_profile.write_text("this is not a valid profile")

    with pytest.raises(ProfileParsingError) as excinfo:
        _get_uuid_from_profile(malformed_profile)

    assert "malformed.md" in str(excinfo.value)


@pytest.mark.parametrize(
    ("alias", "reason"),
    [
        ("", "must not be empty"),
        ("   ", "must not be empty"),
        ("a" * 41, "cannot be longer than 40 characters"),
        ("a\x00b", "contains control characters"),
    ],
)
def test_validate_alias_invalid(alias: str, reason: str):
    """Test that _validate_alias raises InvalidAliasError for invalid aliases."""
    with pytest.raises(InvalidAliasError) as excinfo:
        _validate_alias(alias)
    assert reason in str(excinfo.value)
