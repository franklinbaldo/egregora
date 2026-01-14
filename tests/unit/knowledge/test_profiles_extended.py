"""Extended unit tests for the profiles module."""

from pathlib import Path

import pytest
import yaml

from egregora.knowledge.exceptions import ProfileNotFoundError, ProfileParseError
from egregora.knowledge.profiles import (
    _find_profile_path,
    _get_uuid_from_profile,
    _validate_alias,
    apply_command_to_profile,
    get_opted_out_authors,
    is_opted_out,
    read_profile,
    remove_profile_avatar,
    sync_all_profiles,
    update_profile_avatar,
    write_profile,
)


def test_get_uuid_from_profile_success():
    """Test that _get_uuid_from_profile successfully extracts the UUID from frontmatter."""
    profile_content = """---
uuid: "12345678-1234-5678-1234-567812345678"
---
Profile content."""
    profile_path = Path("test_profile.md")
    profile_path.write_text(profile_content)

    uuid = _get_uuid_from_profile(profile_path)
    assert uuid == "12345678-1234-5678-1234-567812345678"

    profile_path.unlink()


def test_get_uuid_from_profile_fallback():
    """Test that _get_uuid_from_profile falls back to using the filename as the UUID."""
    profile_content = """---
name: "Test User"
---
Profile content."""
    profile_path = Path("87654321-4321-8765-4321-876543210987.md")
    profile_path.write_text(profile_content)

    uuid = _get_uuid_from_profile(profile_path)
    assert uuid == "87654321-4321-8765-4321-876543210987"

    profile_path.unlink()


def test_get_uuid_from_profile_no_uuid():
    """Test that _get_uuid_from_profile raises ProfileParseError when no UUID is found."""
    profile_content = """---
name: "Test User"
---
Profile content."""
    profile_path = Path("test_profile.md")
    profile_path.write_text(profile_content)

    with pytest.raises(ProfileParseError):
        _get_uuid_from_profile(profile_path)

    profile_path.unlink()


def test_validate_alias_success():
    """Test that _validate_alias returns a valid alias."""
    alias = "valid_alias"
    validated_alias = _validate_alias(alias)
    assert validated_alias == "valid_alias"


def test_validate_alias_sanitization():
    """Test that _validate_alias sanitizes special characters."""
    alias = "<script>alert('xss')</script>"
    sanitized_alias = _validate_alias(alias)
    assert sanitized_alias == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"


def test_find_profile_path_new_structure(tmp_path: Path):
    """Test finding a profile in the new structure ({uuid}/index.md)."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    author_dir = profiles_dir / author_uuid
    author_dir.mkdir(parents=True)
    profile_path = author_dir / "index.md"
    profile_path.touch()

    found_path = _find_profile_path(author_uuid, profiles_dir)
    assert found_path == profile_path


def test_find_profile_path_legacy_structure(tmp_path: Path):
    """Test finding a profile in the legacy flat file structure ({uuid}.md)."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    author_uuid = "12345678-1234-5678-1234-567812345678"
    profile_path = profiles_dir / f"{author_uuid}.md"
    profile_path.touch()

    found_path = _find_profile_path(author_uuid, profiles_dir)
    assert found_path == profile_path


def test_find_profile_path_scan_directory(tmp_path: Path):
    """Test finding a profile by scanning the directory for slug-based files."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    author_uuid = "12345678-1234-5678-1234-567812345678"
    profile_content = f'''---
uuid: "{author_uuid}"
---
Profile content.'''
    profile_path = profiles_dir / "some-slug.md"
    profile_path.write_text(profile_content)

    found_path = _find_profile_path(author_uuid, profiles_dir)
    assert found_path == profile_path


def test_find_profile_path_not_found(tmp_path: Path):
    """Test the ProfileNotFoundError case."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    author_uuid = "12345678-1234-5678-1234-567812345678"

    with pytest.raises(ProfileNotFoundError):
        _find_profile_path(author_uuid, profiles_dir)


def test_read_profile_success(tmp_path: Path):
    """Test the success case for read_profile."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    author_dir = profiles_dir / author_uuid
    author_dir.mkdir(parents=True)
    profile_path = author_dir / "index.md"
    profile_content = "This is the profile content."
    profile_path.write_text(profile_content)

    content = read_profile(author_uuid, profiles_dir)
    assert content == profile_content


def test_write_profile_new(tmp_path: Path):
    """Test creating a new profile."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    content = "This is a new profile."

    profile_path_str = write_profile(author_uuid, content, profiles_dir)
    profile_path = Path(profile_path_str)

    assert profile_path.exists()
    assert content in profile_path.read_text()
    assert author_uuid in profile_path.read_text()


def test_write_profile_update(tmp_path: Path):
    """Test updating an existing profile."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    author_dir = profiles_dir / author_uuid
    author_dir.mkdir(parents=True)
    profile_path = author_dir / "index.md"
    profile_path.write_text("Initial content.")

    new_content = "This is the updated content."
    write_profile(author_uuid, new_content, profiles_dir)

    assert new_content in profile_path.read_text()


def test_write_profile_rename(tmp_path: Path):
    """Test renaming a profile when the alias changes."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    author_dir = profiles_dir / author_uuid
    author_dir.mkdir(parents=True)

    initial_profile_content = f'''---
uuid: "{author_uuid}"
alias: "old-alias"
---
Initial content.'''
    legacy_path = profiles_dir / f"{author_uuid}.md"
    legacy_path.write_text(initial_profile_content)

    write_profile(author_uuid, "Updated content.", profiles_dir)

    new_path = author_dir / "index.md"
    assert new_path.exists()
    assert not legacy_path.exists()


def test_apply_command_to_profile_set_alias(tmp_path: Path):
    """Test setting an alias."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    command = {"command": "set", "target": "alias", "value": "new-alias"}
    timestamp = "2024-01-01T12:00:00Z"

    profile_path_str = apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)
    profile_path = Path(profile_path_str)

    assert profile_path.exists()
    content = profile_path.read_text()
    assert "new-alias" in content


def test_apply_command_to_profile_remove_alias(tmp_path: Path):
    """Test removing an alias."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"

    # First, set an alias
    apply_command_to_profile(
        author_uuid,
        {"command": "set", "target": "alias", "value": "old-alias"},
        "2024-01-01T11:00:00Z",
        profiles_dir,
    )

    # Now, remove it
    command = {"command": "remove", "target": "alias"}
    timestamp = "2024-01-01T12:00:00Z"
    profile_path_str = apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)
    profile_path = Path(profile_path_str)

    content = profile_path.read_text()
    assert "Alias: None" in content


def test_apply_command_to_profile_set_bio(tmp_path: Path):
    """Test setting a bio."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    command = {"command": "set", "target": "bio", "value": "This is my bio."}
    timestamp = "2024-01-01T12:00:00Z"

    profile_path_str = apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)
    profile_path = Path(profile_path_str)

    content = profile_path.read_text()
    assert "This is my bio." in content


def test_apply_command_to_profile_opt_out(tmp_path: Path):
    """Test opting out."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    command = {"command": "opt-out", "target": "privacy"}
    timestamp = "2024-01-01T12:00:00Z"

    profile_path_str = apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)
    profile_path = Path(profile_path_str)

    content = profile_path.read_text()
    assert "Status: OPTED OUT" in content


def test_apply_command_to_profile_opt_in(tmp_path: Path):
    """Test opting in."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"

    # First, opt out
    apply_command_to_profile(
        author_uuid, {"command": "opt-out", "target": "privacy"}, "2024-01-01T11:00:00Z", profiles_dir
    )

    # Now, opt in
    command = {"command": "opt-in", "target": "privacy"}
    timestamp = "2024-01-01T12:00:00Z"
    profile_path_str = apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)
    profile_path = Path(profile_path_str)

    content = profile_path.read_text()
    assert "Status: Opted in" in content


def test_is_opted_out_true(tmp_path: Path):
    """Test the case where a user has opted out."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    apply_command_to_profile(
        author_uuid, {"command": "opt-out", "target": "privacy"}, "2024-01-01T12:00:00Z", profiles_dir
    )

    assert is_opted_out(author_uuid, profiles_dir)


def test_is_opted_out_false(tmp_path: Path):
    """Test the case where a user has not opted out."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    write_profile(author_uuid, "Some content.", profiles_dir)

    assert not is_opted_out(author_uuid, profiles_dir)


def test_is_opted_out_no_profile(tmp_path: Path):
    """Test the case where a user does not have a profile."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"

    assert not is_opted_out(author_uuid, profiles_dir)


def test_get_opted_out_authors_mixed(tmp_path: Path):
    """Test with a directory containing opted-out and opted-in users."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    opted_out_uuid = "11111111-1111-1111-1111-111111111111"
    opted_in_uuid = "22222222-2222-2222-2222-222222222222"

    # Opt-out user
    apply_command_to_profile(
        opted_out_uuid, {"command": "opt-out", "target": "privacy"}, "2024-01-01T12:00:00Z", profiles_dir
    )

    # Opt-in user
    write_profile(opted_in_uuid, "Some content.", profiles_dir)

    opted_out_authors = get_opted_out_authors(profiles_dir)
    assert opted_out_authors == {opted_out_uuid}


def test_get_opted_out_authors_empty(tmp_path: Path):
    """Test with an empty directory."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    opted_out_authors = get_opted_out_authors(profiles_dir)
    assert opted_out_authors == set()


def test_get_opted_out_authors_malformed(tmp_path: Path):
    """Test that a malformed but opted-out profile is skipped."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    malformed_profile = profiles_dir / "malformed.md"
    malformed_profile.write_text("Status: OPTED OUT")

    opted_out_authors = get_opted_out_authors(profiles_dir)
    assert opted_out_authors == set()


def test_update_profile_avatar(tmp_path: Path):
    """Test updating an avatar."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    avatar_url = "http://example.com/avatar.png"
    timestamp = "2024-01-01T12:00:00Z"

    profile_path_str = update_profile_avatar(author_uuid, avatar_url, timestamp, profiles_dir)
    profile_path = Path(profile_path_str)

    content = profile_path.read_text()
    assert avatar_url in content


def test_remove_profile_avatar(tmp_path: Path):
    """Test removing an avatar."""
    profiles_dir = tmp_path / "profiles"
    author_uuid = "12345678-1234-5678-1234-567812345678"
    avatar_url = "http://example.com/avatar.png"
    timestamp = "2024-01-01T12:00:00Z"

    # First, set an avatar
    update_profile_avatar(author_uuid, avatar_url, timestamp, profiles_dir)

    # Now, remove it
    remove_timestamp = "2024-01-01T13:00:00Z"
    profile_path_str = remove_profile_avatar(author_uuid, remove_timestamp, profiles_dir)
    profile_path = Path(profile_path_str)

    content = profile_path.read_text()
    assert avatar_url not in content
    assert "avatar:" not in content


def test_sync_all_profiles_mixed(tmp_path: Path):
    """Test syncing profiles from both legacy flat and new nested structures."""
    site_root = tmp_path
    profiles_dir = site_root / "profiles"
    profiles_dir.mkdir()

    # Legacy profile
    legacy_uuid = "11111111-1111-1111-1111-111111111111"
    legacy_profile = profiles_dir / f"{legacy_uuid}.md"
    legacy_profile.write_text(f"---\nuuid: {legacy_uuid}\nalias: legacy-user\n---")

    # New profile
    new_uuid = "22222222-2222-2222-2222-222222222222"
    new_author_dir = profiles_dir / new_uuid
    new_author_dir.mkdir()
    new_profile = new_author_dir / "index.md"
    new_profile.write_text(f"---\nuuid: {new_uuid}\nalias: new-user\n---")

    count = sync_all_profiles(profiles_dir)
    assert count == 2

    authors_yml_path = site_root / ".authors.yml"
    assert authors_yml_path.exists()
    with authors_yml_path.open("r") as f:
        authors = yaml.safe_load(f)

    assert legacy_uuid in authors
    assert authors[legacy_uuid]["name"] == "legacy-user"
    assert new_uuid in authors
    assert authors[new_uuid]["name"] == "new-user"
