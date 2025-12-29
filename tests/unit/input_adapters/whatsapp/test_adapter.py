"""Unit tests for the WhatsApp input adapter."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from egregora.input_adapters.whatsapp.adapter import WhatsAppAdapter
from egregora.input_adapters.whatsapp.exceptions import (
    InvalidMediaReferenceError,
    InvalidZipFileError,
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


def test_deliver_media_raises_missing_zip_path_error(adapter: WhatsAppAdapter) -> None:
    """Test `deliver_media` raises MissingZipPathError if zip_path is missing."""
    with pytest.raises(MissingZipPathError):
        adapter.deliver_media("some_media.jpg")


def test_deliver_media_raises_zip_path_not_found_error(adapter: WhatsAppAdapter, tmp_path: Path) -> None:
    """Test `deliver_media` raises ZipPathNotFoundError if zip_path does not exist."""
    non_existent_zip = tmp_path / "non_existent.zip"
    with pytest.raises(ZipPathNotFoundError):
        adapter.deliver_media("some_media.jpg", zip_path=non_existent_zip)


def test_deliver_media_raises_invalid_media_reference_error(adapter: WhatsAppAdapter) -> None:
    """Test `deliver_media` raises InvalidMediaReferenceError for suspicious media references."""
    suspicious_references = [
        "../some_media.jpg",
        "/etc/passwd",
        "some_dir/../../some_media.jpg",
    ]
    for ref in suspicious_references:
        with pytest.raises(InvalidMediaReferenceError):
            adapter.deliver_media(ref)


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
        patch("egregora.input_adapters.whatsapp.adapter.parse_source") as mock_parse_source,
    ):
        mock_parse_source.side_effect = WhatsAppParsingError("mock error")
        with pytest.raises(WhatsAppAdapterError):
            adapter.parse(zip_path)


def test_deliver_media_raises_on_missing_file(adapter: WhatsAppAdapter, tmp_path: Path):
    """Test `deliver_media` raises MediaNotFoundError when a file is not in the zip."""
    # Create a dummy zip file
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("some_other_file.txt", "dummy content")

    # Call deliver_media with a non-existent file and assert it raises
    with pytest.raises(MediaNotFoundError) as exc_info:
        adapter.deliver_media("non_existent_file.jpg", zip_path=zip_path)

    assert "non_existent_file.jpg" in str(exc_info.value)
    assert str(zip_path) in str(exc_info.value)
