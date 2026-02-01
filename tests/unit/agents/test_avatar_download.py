"""Unit tests for avatar download logic."""

import uuid
from unittest.mock import patch

import httpx
import pytest
import respx

from egregora.agents.avatar import (
    AvatarProcessingError,
    _download_avatar_with_client,
)

FAKE_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")

# Minimal valid 1x1 PNG
VALID_PNG_CONTENT = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def mock_media_dir(tmp_path):
    """Create a temporary media directory."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "images").mkdir()
    return media_dir


@pytest.fixture
def mock_client():
    """Create a mock httpx client."""
    return httpx.Client()


@patch("egregora.agents.avatar._generate_avatar_uuid", return_value=FAKE_UUID)
@respx.mock
def test_download_avatar_success(_, mock_media_dir, mock_client):
    """Test successful avatar download."""
    url = "http://example.com/avatar.png"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=VALID_PNG_CONTENT, headers={"Content-Type": "image/png"})
    )

    avatar_uuid, avatar_path = _download_avatar_with_client(mock_client, url, mock_media_dir)

    assert avatar_uuid == FAKE_UUID
    assert avatar_path == mock_media_dir / "images" / f"{FAKE_UUID}.png"
    assert avatar_path.read_bytes() == VALID_PNG_CONTENT


@respx.mock
def test_download_avatar_http_error(mock_media_dir, mock_client):
    """Test HTTP error handling."""
    url = "http://example.com/404.png"
    respx.get(url).mock(return_value=httpx.Response(404))

    with pytest.raises(AvatarProcessingError) as exc:
        _download_avatar_with_client(mock_client, url, mock_media_dir)

    assert "Failed to download avatar" in str(exc.value)


@respx.mock
def test_download_avatar_too_many_redirects(mock_media_dir, mock_client):
    """Test TooManyRedirects handling."""
    url = "http://example.com/loop"
    respx.get(url).mock(side_effect=httpx.TooManyRedirects("Too many redirects", request=None))

    with pytest.raises(AvatarProcessingError) as exc:
        _download_avatar_with_client(mock_client, url, mock_media_dir)

    assert "Too many redirects" in str(exc.value)


@respx.mock
def test_download_avatar_invalid_content_type(mock_media_dir, mock_client):
    """Test invalid content type handling."""
    url = "http://example.com/text.txt"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=b"text", headers={"Content-Type": "text/plain"})
    )

    with pytest.raises(AvatarProcessingError) as exc:
        _download_avatar_with_client(mock_client, url, mock_media_dir)

    assert "Invalid image MIME type" in str(exc.value)


@patch("egregora.agents.avatar._save_avatar_file")
@patch("egregora.agents.avatar._generate_avatar_uuid", return_value=FAKE_UUID)
@respx.mock
def test_download_avatar_os_error(_, mock_save, mock_media_dir, mock_client):
    """Test file system error handling."""
    url = "http://example.com/avatar.png"
    respx.get(url).mock(
        return_value=httpx.Response(200, content=VALID_PNG_CONTENT, headers={"Content-Type": "image/png"})
    )

    mock_save.side_effect = OSError("Disk full")

    with pytest.raises(AvatarProcessingError) as exc:
        _download_avatar_with_client(mock_client, url, mock_media_dir)

    assert "Failed to save avatar" in str(exc.value)


def test_detect_mime_type_valid():
    from egregora.agents.avatar import _detect_mime_type

    assert _detect_mime_type(b"\xff\xd8\xff") == "image/jpeg"
    assert _detect_mime_type(b"\x89PNG\r\n\x1a\n") == "image/png"
    assert _detect_mime_type(b"GIF87a") == "image/gif"
    assert _detect_mime_type(b"RIFF\x20\x00\x00\x00WEBP") == "image/webp"


def test_detect_mime_type_invalid_riff():
    from egregora.agents.avatar import _detect_mime_type, AvatarProcessingError

    # Too short for RIFF check
    assert _detect_mime_type(b"RIF") is None

    # RIFF but too short for WEBP check
    with pytest.raises(AvatarProcessingError, match="File too small"):
        _detect_mime_type(b"RIFF\x00")

    # RIFF but not WEBP
    with pytest.raises(AvatarProcessingError, match="RIFF file is not WEBP"):
        _detect_mime_type(b"RIFF\x20\x00\x00\x00AVI ")


def test_detect_mime_type_unknown():
    from egregora.agents.avatar import _detect_mime_type

    assert _detect_mime_type(b"unknown") is None
