"""Tests for avatar processing functionality."""

import uuid
from pathlib import Path

import pytest

from egregora.agents.tools.profiler import (
    get_avatar_info,
    remove_profile_avatar,
    update_profile_avatar,
)
from egregora.enrichment.avatar import (
    AvatarProcessingError,
    _generate_avatar_uuid,
    _validate_image_format,
)
from egregora.ingestion.parser import parse_egregora_command


class TestCommandParsing:
    """Test avatar command parsing."""

    def test_parse_set_avatar_with_url(self):
        """Test parsing 'set avatar' command with URL."""
        result = parse_egregora_command("/egregora set avatar https://example.com/avatar.jpg")
        assert result is not None
        assert result["command"] == "set"
        assert result["target"] == "avatar"
        assert result["value"] == "https://example.com/avatar.jpg"

    def test_parse_set_avatar_with_quoted_url(self):
        """Test parsing 'set avatar' command with quoted URL."""
        result = parse_egregora_command('/egregora set avatar "https://example.com/avatar.jpg"')
        assert result is not None
        assert result["command"] == "set"
        assert result["target"] == "avatar"
        # Value should have quotes stripped
        assert result["value"] == "https://example.com/avatar.jpg"

    def test_parse_unset_avatar(self):
        """Test parsing 'unset avatar' command."""
        result = parse_egregora_command("/egregora unset avatar")
        assert result is not None
        assert result["command"] == "unset"
        assert result["target"] == "avatar"
        assert result["value"] is None

    def test_parse_unset_avatar_case_insensitive(self):
        """Test parsing 'unset avatar' command is case-insensitive."""
        result = parse_egregora_command("/EGREGORA UNSET AVATAR")
        assert result is not None
        assert result["command"] == "unset"
        assert result["target"] == "avatar"


class TestAvatarValidation:
    """Test avatar validation functions."""

    def test_validate_image_format_valid(self):
        """Test validation accepts valid image formats."""
        assert _validate_image_format("avatar.jpg") == ".jpg"
        assert _validate_image_format("avatar.jpeg") == ".jpeg"
        assert _validate_image_format("avatar.png") == ".png"
        assert _validate_image_format("avatar.gif") == ".gif"
        assert _validate_image_format("avatar.webp") == ".webp"

    def test_validate_image_format_case_insensitive(self):
        """Test validation is case-insensitive."""
        assert _validate_image_format("AVATAR.JPG") == ".jpg"
        assert _validate_image_format("avatar.PNG") == ".png"

    def test_validate_image_format_invalid(self):
        """Test validation rejects invalid formats."""
        with pytest.raises(AvatarProcessingError):
            _validate_image_format("avatar.txt")

        with pytest.raises(AvatarProcessingError):
            _validate_image_format("avatar.pdf")

    def test_generate_avatar_uuid_deterministic(self):
        """Test UUID generation is deterministic."""
        content = b"test image content"
        slug = "test-group"

        uuid1 = _generate_avatar_uuid(content, slug)
        uuid2 = _generate_avatar_uuid(content, slug)

        assert uuid1 == uuid2
        assert isinstance(uuid1, uuid.UUID)

    def test_generate_avatar_uuid_different_content(self):
        """Test different content produces different UUIDs."""
        slug = "test-group"

        uuid1 = _generate_avatar_uuid(b"content1", slug)
        uuid2 = _generate_avatar_uuid(b"content2", slug)

        assert uuid1 != uuid2


class TestProfileAvatarManagement:
    """Test profile avatar management functions."""

    def test_update_profile_avatar_approved(self, tmp_path):
        """Test updating profile with approved avatar."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        author_uuid = "test-author-uuid"
        avatar_uuid = "avatar-uuid-123"
        avatar_path = Path("media/avatars/avatar.jpg")
        timestamp = "2025-01-15T10:00:00"

        result = update_profile_avatar(
            author_uuid=author_uuid,
            avatar_uuid=avatar_uuid,
            avatar_path=avatar_path,
            moderation_status="approved",
            moderation_reason="Looks good",
            timestamp=timestamp,
            profiles_dir=profiles_dir,
        )

        # Check profile was created
        profile_path = profiles_dir / f"{author_uuid}.md"
        assert profile_path.exists()

        content = profile_path.read_text()
        assert "## Avatar" in content
        assert avatar_uuid in content
        assert "✅ Approved" in content
        assert timestamp in content

    def test_update_profile_avatar_questionable(self, tmp_path):
        """Test updating profile with questionable avatar."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        author_uuid = "test-author-uuid"

        result = update_profile_avatar(
            author_uuid=author_uuid,
            avatar_uuid="avatar-123",
            avatar_path=Path("media/avatars/avatar.jpg"),
            moderation_status="questionable",
            moderation_reason="Needs manual review",
            timestamp="2025-01-15T10:00:00",
            profiles_dir=profiles_dir,
        )

        profile_path = profiles_dir / f"{author_uuid}.md"
        content = profile_path.read_text()

        assert "⚠️ Pending Review" in content
        assert "Needs manual review" in content

    def test_update_profile_avatar_blocked(self, tmp_path):
        """Test updating profile with blocked avatar."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        author_uuid = "test-author-uuid"

        result = update_profile_avatar(
            author_uuid=author_uuid,
            avatar_uuid="avatar-123",
            avatar_path=Path("media/avatars/avatar.jpg"),
            moderation_status="blocked",
            moderation_reason="Inappropriate content",
            timestamp="2025-01-15T10:00:00",
            profiles_dir=profiles_dir,
        )

        profile_path = profiles_dir / f"{author_uuid}.md"
        content = profile_path.read_text()

        assert "❌ Blocked" in content
        assert "Inappropriate content" in content

    def test_remove_profile_avatar(self, tmp_path):
        """Test removing avatar from profile."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        author_uuid = "test-author-uuid"

        # First set an avatar
        update_profile_avatar(
            author_uuid=author_uuid,
            avatar_uuid="avatar-123",
            avatar_path=Path("media/avatars/avatar.jpg"),
            moderation_status="approved",
            moderation_reason="",
            timestamp="2025-01-15T10:00:00",
            profiles_dir=profiles_dir,
        )

        # Now remove it
        timestamp = "2025-01-15T11:00:00"
        remove_profile_avatar(author_uuid, timestamp, profiles_dir)

        profile_path = profiles_dir / f"{author_uuid}.md"
        content = profile_path.read_text()

        assert "None (removed on" in content
        assert timestamp in content

    def test_get_avatar_info_approved(self, tmp_path):
        """Test getting avatar info for approved avatar."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        author_uuid = "test-author-uuid"
        avatar_uuid = "avatar-uuid-123"
        avatar_path = Path("media/avatars/avatar.jpg")

        update_profile_avatar(
            author_uuid=author_uuid,
            avatar_uuid=avatar_uuid,
            avatar_path=avatar_path,
            moderation_status="approved",
            moderation_reason="",
            timestamp="2025-01-15T10:00:00",
            profiles_dir=profiles_dir,
        )

        info = get_avatar_info(author_uuid, profiles_dir)

        assert info is not None
        assert info["uuid"] == avatar_uuid
        assert info["status"] == "approved"
        assert str(avatar_path) in info["path"]

    def test_get_avatar_info_no_avatar(self, tmp_path):
        """Test getting avatar info when no avatar exists."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        info = get_avatar_info("nonexistent-author", profiles_dir)
        assert info is None

    def test_get_avatar_info_after_removal(self, tmp_path):
        """Test getting avatar info after removal returns None."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        author_uuid = "test-author-uuid"

        # Set and then remove avatar
        update_profile_avatar(
            author_uuid=author_uuid,
            avatar_uuid="avatar-123",
            avatar_path=Path("media/avatars/avatar.jpg"),
            moderation_status="approved",
            moderation_reason="",
            timestamp="2025-01-15T10:00:00",
            profiles_dir=profiles_dir,
        )

        remove_profile_avatar(author_uuid, "2025-01-15T11:00:00", profiles_dir)

        info = get_avatar_info(author_uuid, profiles_dir)
        assert info is None
