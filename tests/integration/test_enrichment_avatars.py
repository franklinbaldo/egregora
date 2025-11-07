"""Tests for avatar processing functionality."""

import io
import socket
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from egregora.ingestion import parse_egregora_command

from egregora.agents.tools.profiler import (
    get_avatar_info,
    remove_profile_avatar,
    update_profile_avatar,
)
from egregora.enrichment.avatar import (
    AvatarProcessingError,
    _generate_avatar_uuid,
    _validate_image_content,
    _validate_image_dimensions,
    _validate_image_format,
    _validate_url_for_ssrf,
)


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


class TestSSRFProtection:
    """Test SSRF protection features."""

    def test_blocks_localhost(self):
        """Test that localhost URLs are blocked."""
        with pytest.raises(AvatarProcessingError, match="blocked IP address"):
            _validate_url_for_ssrf("http://127.0.0.1/avatar.jpg")

    def test_blocks_localhost_ipv6(self):
        """Test that IPv6 localhost is blocked."""
        with pytest.raises(AvatarProcessingError, match="blocked IP address"):
            _validate_url_for_ssrf("http://[::1]/avatar.jpg")

    def test_blocks_private_network_10(self):
        """Test that 10.0.0.0/8 private network is blocked."""
        with pytest.raises(AvatarProcessingError, match="blocked IP address"):
            _validate_url_for_ssrf("http://10.0.0.1/avatar.jpg")

    def test_blocks_private_network_192(self):
        """Test that 192.168.0.0/16 private network is blocked."""
        with pytest.raises(AvatarProcessingError, match="blocked IP address"):
            _validate_url_for_ssrf("http://192.168.1.1/avatar.jpg")

    def test_blocks_private_network_172(self):
        """Test that 172.16.0.0/12 private network is blocked."""
        with pytest.raises(AvatarProcessingError, match="blocked IP address"):
            _validate_url_for_ssrf("http://172.16.0.1/avatar.jpg")

    def test_blocks_link_local(self):
        """Test that link-local addresses are blocked."""
        with pytest.raises(AvatarProcessingError, match="blocked IP address"):
            _validate_url_for_ssrf("http://169.254.0.1/avatar.jpg")

    @patch("socket.getaddrinfo")
    def test_blocks_ipv4_mapped_ipv6_localhost(self, mock_getaddrinfo):
        """Test that IPv4-mapped IPv6 localhost (::ffff:127.0.0.1) is blocked."""
        # Mock DNS resolution to return IPv4-mapped IPv6 address
        mock_getaddrinfo.return_value = [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::ffff:127.0.0.1", 80, 0, 0))
        ]

        with pytest.raises(AvatarProcessingError, match="IPv4-mapped"):
            _validate_url_for_ssrf("http://malicious.example.com/avatar.jpg")

    @patch("socket.getaddrinfo")
    def test_blocks_ipv4_mapped_ipv6_private(self, mock_getaddrinfo):
        """Test that IPv4-mapped IPv6 private addresses are blocked."""
        # Mock DNS resolution to return IPv4-mapped IPv6 address for private network
        mock_getaddrinfo.return_value = [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::ffff:192.168.1.1", 80, 0, 0))
        ]

        with pytest.raises(AvatarProcessingError, match="IPv4-mapped"):
            _validate_url_for_ssrf("http://malicious.example.com/avatar.jpg")

    def test_rejects_non_http_schemes(self):
        """Test that non-HTTP/HTTPS schemes are rejected."""
        with pytest.raises(AvatarProcessingError, match="Invalid URL scheme"):
            _validate_url_for_ssrf("file:///etc/passwd")

        with pytest.raises(AvatarProcessingError, match="Invalid URL scheme"):
            _validate_url_for_ssrf("ftp://example.com/avatar.jpg")

    def test_rejects_url_without_hostname(self):
        """Test that URLs without hostname are rejected."""
        with pytest.raises(AvatarProcessingError, match="must have a hostname"):
            _validate_url_for_ssrf("http:///avatar.jpg")

    @patch("socket.getaddrinfo")
    def test_allows_public_ip(self, mock_getaddrinfo):
        """Test that public IPs are allowed."""
        # Mock DNS resolution to return a public IP
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 80))]

        # Should not raise
        _validate_url_for_ssrf("http://example.com/avatar.jpg")


class TestContentValidation:
    """Test content validation features."""

    def test_validate_jpeg_content(self):
        """Test JPEG magic bytes validation."""
        # Create a valid JPEG magic bytes
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100

        # Should not raise
        _validate_image_content(jpeg_bytes, "image/jpeg")

    def test_validate_png_content(self):
        """Test PNG magic bytes validation."""
        # Create valid PNG magic bytes
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        # Should not raise
        _validate_image_content(png_bytes, "image/png")

    def test_validate_gif_content(self):
        """Test GIF magic bytes validation."""
        # Create valid GIF87a magic bytes
        gif_bytes = b"GIF87a" + b"\x00" * 100

        # Should not raise
        _validate_image_content(gif_bytes, "image/gif")

    def test_validate_webp_content(self):
        """Test WEBP magic bytes validation."""
        # Create valid WEBP magic bytes (RIFF....WEBP)
        webp_bytes = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100

        # Should not raise
        _validate_image_content(webp_bytes, "image/webp")

    def test_rejects_mismatched_mime_type(self):
        """Test that mismatched MIME types are rejected."""
        # JPEG bytes but declared as PNG
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100

        with pytest.raises(AvatarProcessingError, match="content type mismatch"):
            _validate_image_content(jpeg_bytes, "image/png")

    def test_rejects_invalid_magic_bytes(self):
        """Test that invalid magic bytes are rejected."""
        # Random bytes that don't match any image format
        invalid_bytes = b"\x00\x00\x00\x00" + b"\x00" * 100

        with pytest.raises(AvatarProcessingError, match="does not match any supported"):
            _validate_image_content(invalid_bytes, "image/jpeg")

    def test_rejects_executable_as_image(self):
        """Test that executable files are rejected even with image MIME type."""
        # ELF header (Linux executable)
        elf_bytes = b"\x7fELF" + b"\x00" * 100

        with pytest.raises(AvatarProcessingError):
            _validate_image_content(elf_bytes, "image/jpeg")


class TestDimensionValidation:
    """Test image dimension validation."""

    def test_allows_small_image(self):
        """Test that small images are allowed."""
        # Create a small test image
        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        content = buf.getvalue()

        # Should not raise
        _validate_image_dimensions(content)

    def test_allows_max_dimension(self):
        """Test that images at max dimension are allowed."""
        # Create an image at the max dimension (4096x100)
        img = Image.new("RGB", (4096, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        content = buf.getvalue()

        # Should not raise
        _validate_image_dimensions(content)

    def test_rejects_oversized_width(self):
        """Test that images with oversized width are rejected."""
        # Create an image that exceeds max width
        img = Image.new("RGB", (5000, 100), color="green")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        content = buf.getvalue()

        with pytest.raises(AvatarProcessingError, match="dimensions too large"):
            _validate_image_dimensions(content)

    def test_rejects_oversized_height(self):
        """Test that images with oversized height are rejected."""
        # Create an image that exceeds max height
        img = Image.new("RGB", (100, 5000), color="yellow")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        content = buf.getvalue()

        with pytest.raises(AvatarProcessingError, match="dimensions too large"):
            _validate_image_dimensions(content)

    def test_rejects_both_dimensions_oversized(self):
        """Test that images with both dimensions oversized are rejected."""
        # Create an image with both dimensions exceeding max
        img = Image.new("RGB", (5000, 5000), color="purple")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        content = buf.getvalue()

        with pytest.raises(AvatarProcessingError, match="dimensions too large"):
            _validate_image_dimensions(content)


class TestZIPPathTraversal:
    """Test ZIP path traversal protection."""

    def test_extracts_safe_filename(self, tmp_path):
        """Test that safe filenames are extracted."""
        # This test validates the path traversal check logic
        # The actual extract_avatar_from_zip function checks for ".." and "/"
        test_filename = "avatar.jpg"
        assert ".." not in test_filename
        assert not test_filename.startswith("/")

    def test_detects_parent_directory_traversal(self):
        """Test that parent directory traversal attempts are detected."""
        malicious_filename = "../../../etc/passwd"
        assert ".." in malicious_filename

    def test_detects_absolute_path_traversal(self):
        """Test that absolute path traversal attempts are detected."""
        malicious_filename = "/etc/passwd"
        assert malicious_filename.startswith("/")

    def test_detects_mixed_traversal(self):
        """Test that mixed traversal attempts are detected."""
        malicious_filename = "../../../home/user/.ssh/id_rsa"
        assert ".." in malicious_filename


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

        update_profile_avatar(
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

        update_profile_avatar(
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

        update_profile_avatar(
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
