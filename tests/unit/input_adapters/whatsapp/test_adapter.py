"""Unit tests for the WhatsAppAdapter."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.input_adapters.whatsapp.adapter import WhatsAppAdapter
from egregora.input_adapters.whatsapp.exceptions import (
    InvalidMediaReferenceError,
    InvalidZipFileError,
    MediaExtractionError,
    MediaNotFoundError,
    MissingZipPathError,
    WhatsAppAdapterError,
    WhatsAppParsingError,
    ZipPathNotFoundError,
)


@pytest.fixture
def adapter() -> WhatsAppAdapter:
    """Return a WhatsAppAdapter instance."""
    return WhatsAppAdapter()


def test_parse_raises_invalid_zip_error_on_bad_zip(adapter: WhatsAppAdapter, tmp_path: Path) -> None:
    """Test `parse` raises InvalidZipFileError on a bad zip file."""
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_text("not a zip file")

    with pytest.raises(InvalidZipFileError):
        adapter.parse(bad_zip)


def test_deliver_media_raises_invalid_zip_error_on_bad_zip(adapter: WhatsAppAdapter, tmp_path: Path) -> None:
    """Test `deliver_media` raises InvalidZipFileError on a bad zip file."""
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_text("not a zip file")

    with pytest.raises(InvalidZipFileError):
        adapter.deliver_media("some_media.jpg", zip_path=bad_zip)


def test_deliver_media_raises_media_extraction_error_on_missing_zip_path(adapter: WhatsAppAdapter) -> None:
    """Test `deliver_media` raises MissingZipPathError if zip_path is missing."""
    with pytest.raises(MissingZipPathError):
        adapter.deliver_media("some_media.jpg")


def test_parse_raises_adapter_error_on_parsing_error(adapter: WhatsAppAdapter, tmp_path: Path) -> None:
    """Test `parse` raises WhatsAppAdapterError on a parsing error."""
    # We can use a valid zip file here, as the parsing is mocked.
    zip_path = tmp_path / "good.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("_chat.txt", "some content")

    with (
        patch(
            "egregora.input_adapters.whatsapp.adapter.discover_chat_file",
            return_value=("Test Group", "_chat.txt"),
        ),
        patch("egregora.input_adapters.whatsapp.parsing.parse_source") as mock_parse_source,
    ):
        mock_parse_source.side_effect = WhatsAppParsingError
        with pytest.raises(WhatsAppAdapterError):
            adapter.parse(zip_path)


class TestWhatsAppAdapterMediaDelivery:
    """Tests for the deliver_media method and its helpers."""

    def test_deliver_media_with_invalid_reference_raises_exception(self, adapter: WhatsAppAdapter):
        """Verify that path traversal attempts raise InvalidMediaReferenceError."""
        with pytest.raises(InvalidMediaReferenceError):
            adapter.deliver_media("../../../etc/passwd", zip_path=Path("dummy.zip"))

    def test_deliver_media_without_zip_path_raises_exception(self, adapter: WhatsAppAdapter):
        """Verify that a missing zip_path kwarg raises MissingZipPathError."""
        with pytest.raises(MissingZipPathError):
            adapter.deliver_media("some_media.jpg")

    def test_deliver_media_with_nonexistent_zip_path_raises_exception(self, adapter: WhatsAppAdapter, mocker):
        """Verify that a zip_path that doesn't exist raises ZipPathNotFoundError."""
        mocker.patch("pathlib.Path.exists", return_value=False)
        with pytest.raises(ZipPathNotFoundError):
            adapter.deliver_media("some_media.jpg", zip_path=Path("nonexistent.zip"))

    def test_deliver_media_with_media_not_in_zip_raises_exception(self, adapter: WhatsAppAdapter, tmp_path):
        """Verify that a missing media file inside the zip raises MediaNotFoundError."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("not_the_file.txt", "content")

        with pytest.raises(MediaNotFoundError):
            adapter.deliver_media("missing_media.jpg", zip_path=zip_path)

    def test_deliver_media_with_bad_zip_file_raises_exception(self, adapter: WhatsAppAdapter, tmp_path):
        """Verify that a corrupted zip file raises InvalidZipFileError."""
        zip_path = tmp_path / "bad.zip"
        zip_path.write_text("this is not a zip file")

        with pytest.raises(InvalidZipFileError):
            adapter.deliver_media("some_media.jpg", zip_path=zip_path)

    @patch("zipfile.ZipFile")
    def test_deliver_media_with_os_error_raises_exception(
        self, mock_zipfile, adapter: WhatsAppAdapter, tmp_path
    ):
        """Verify that OS-level errors during extraction raise MediaExtractionError."""
        zip_path = tmp_path / "test.zip"
        zip_path.touch()  # Create the file

        mock_zip_instance = MagicMock()
        mock_zip_instance.read.side_effect = OSError("Disk full")
        mock_zip_instance.infolist.return_value = [zipfile.ZipInfo("some_media.jpg")]

        mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

        with pytest.raises(MediaExtractionError):
            adapter.deliver_media("some_media.jpg", zip_path=zip_path)
