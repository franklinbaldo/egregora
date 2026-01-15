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
