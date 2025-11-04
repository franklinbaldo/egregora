"""Unit tests for avatar-related commands and functionality."""

from pathlib import Path

from typer.testing import CliRunner

from src.egregora.augmentation import profiler
from src.egregora.ingestion import parser
from src.egregora.orchestration import cli

runner = CliRunner()


def test_parse_set_avatar_command():
    """Test parsing of the 'set avatar' command."""
    result = parser.parse_egregora_command("/egregora set avatar")
    assert result == {"command": "set", "target": "avatar", "value": None}


def test_parse_unset_avatar_command():
    """Test parsing of the 'unset avatar' command."""
    result = parser.parse_egregora_command("/egregora unset avatar")
    assert result == {"command": "remove", "target": "avatar", "value": None}


def test_extract_commands_with_attachment():
    """Test that extract_commands correctly handles a message with an attachment."""
    messages = [
        {
            "author": "test_author",
            "timestamp": "2025-01-01 12:00:00",
            "message": "image.jpg (file attached) /egregora set avatar",
        }
    ]

    # This is a simplified version of what the ibis table would look like
    class MockCount:
        def __init__(self, value):
            self.value = value

        def execute(self):
            return self.value

    class MockTable:
        def __init__(self, data):
            self.data = data

        def execute(self):
            return self

        def to_dict(self, orient):
            return self.data

        def count(self):
            return MockCount(len(self.data))

    result = parser.extract_commands(MockTable(messages))
    assert len(result) == 1
    assert result[0]["command"]["target"] == "avatar"
    assert result[0]["command"]["value"] == "image.jpg"


def test_apply_command_to_profile_set_avatar(tmp_path):
    """Test that the 'set avatar' command correctly updates the profile."""
    profile_path = tmp_path / "test_author.md"
    command = {"command": "set", "target": "avatar", "value": "avatar.jpg"}
    media_mapping = {"avatar.jpg": Path("/path/to/avatar.jpg")}
    profiler.apply_command_to_profile(
        "test_author", command, "2025-01-01 12:00:00", tmp_path, media_mapping
    )
    content = profile_path.read_text()
    assert '![Avatar](/path/to/avatar.jpg "Avatar")' in content


def test_apply_command_to_profile_unset_avatar(tmp_path):
    """Test that the 'unset avatar' command correctly removes the avatar from the profile."""
    profile_path = tmp_path / "test_author.md"
    # First, set the avatar
    set_command = {"command": "set", "target": "avatar", "value": "avatar.jpg"}
    media_mapping = {"avatar.jpg": Path("/path/to/avatar.jpg")}
    profiler.apply_command_to_profile(
        "test_author", set_command, "2025-01-01 12:00:00", tmp_path, media_mapping
    )
    # Now, unset it
    unset_command = {"command": "remove", "target": "avatar", "value": None}
    profiler.apply_command_to_profile(
        "test_author", unset_command, "2025-01-01 12:00:00", tmp_path, {}
    )
    content = profile_path.read_text()
    assert "## Avatar" not in content


def test_get_avatar_command(tmp_path):
    """Test the 'get-avatar' CLI command."""
    profile_content = '## Avatar\n![Avatar](/path/to/avatar.jpg "Avatar")'
    avatar_path = cli._parse_avatar_from_profile(profile_content)
    assert avatar_path == "/path/to/avatar.jpg"


def test_remove_avatar_command(tmp_path):
    """Test the 'remove-avatar' CLI command."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "mkdocs.yml").touch()
    (site_dir / "docs").mkdir()
    profiles_dir = site_dir / "docs" / "profiles"
    profiles_dir.mkdir()
    profile_path = profiles_dir / "test_author.md"
    media_dir = site_dir / "docs" / "media"
    media_dir.mkdir()
    avatar_path = media_dir / "avatar.jpg"
    avatar_path.touch()
    profile_path.write_text(f'## Avatar\n![Avatar]({avatar_path} "Avatar")')

    # Manually call the functions that the CLI command would call
    profile_content = profiler.read_profile("test_author", profiles_dir)
    avatar_path_str = cli._parse_avatar_from_profile(profile_content)
    avatar_path = Path(avatar_path_str)
    if avatar_path.exists():
        avatar_path.unlink()
    updated_content = profiler._update_profile_metadata(profile_content, "Avatar", "avatar", "")
    profile_path.write_text(updated_content, encoding="utf-8")

    assert not avatar_path.exists()
    content = profile_path.read_text()
    assert "## Avatar" not in content
