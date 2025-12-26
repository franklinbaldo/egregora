"""Unit tests for the WhatsApp input adapter."""

import zipfile
from pathlib import Path

import pytest

from egregora.input_adapters.whatsapp.adapter import WhatsAppAdapter
from egregora.input_adapters.whatsapp.exceptions import (
    InvalidMediaReferenceError,
    MediaExtractionError,
    MediaNotFoundError,
    MissingZipPathError,
    ZipPathNotFoundError,
)


@pytest.fixture
def adapter() -> WhatsAppAdapter:
    """Returns a WhatsAppAdapter instance."""
    return WhatsAppAdapter()


@pytest.fixture
def mock_zip_path(tmp_path: Path) -> Path:
    """Creates a dummy zip file for testing."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("media.jpg", b"fake image data")
    return zip_path


def test_deliver_media_raises_for_invalid_reference(adapter: WhatsAppAdapter):
    """
    Verify that deliver_media raises InvalidMediaReferenceError for a
    suspicious media reference.
    """
    with pytest.raises(InvalidMediaReferenceError):
        adapter.deliver_media("../etc/passwd", zip_path=Path("dummy.zip"))


def test_deliver_media_raises_for_missing_zip_path(adapter: WhatsAppAdapter):
    """
    Verify that deliver_media raises MissingZipPathError when the
    zip_path kwarg is not provided.
    """
    with pytest.raises(MissingZipPathError):
        adapter.deliver_media("media.jpg")


def test_deliver_media_raises_for_nonexistent_zip(adapter: WhatsAppAdapter):
    """
    Verify that deliver_media raises ZipPathNotFoundError when the
    provided zip_path does not exist.
    """
    non_existent_path = Path("/non/existent/path.zip")
    with pytest.raises(ZipPathNotFoundError):
        adapter.deliver_media("media.jpg", zip_path=non_existent_path)


def test_deliver_media_raises_for_media_not_found(adapter: WhatsAppAdapter, mock_zip_path: Path):
    """
    Verify that deliver_media raises MediaNotFoundError when the media
    file is not found in the zip archive.
    """
    with pytest.raises(MediaNotFoundError):
        adapter.deliver_media("not_found.jpg", zip_path=mock_zip_path)


def test_deliver_media_raises_for_bad_zip_file(adapter: WhatsAppAdapter, tmp_path: Path):
    """
    Verify that deliver_media raises MediaExtractionError for a corrupt
    or invalid ZIP file.
    """
    bad_zip_path = tmp_path / "bad.zip"
    bad_zip_path.write_text("this is not a zip file")
    with pytest.raises(MediaExtractionError):
        adapter.deliver_media("media.jpg", zip_path=bad_zip_path)
