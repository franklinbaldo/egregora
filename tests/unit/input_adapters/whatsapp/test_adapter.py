"""Unit tests for the WhatsApp input adapter."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from egregora.input_adapters.whatsapp.adapter import WhatsAppAdapter
from egregora.input_adapters.whatsapp.exceptions import (
    InvalidZipFileError,
    MediaExtractionError,
    WhatsAppAdapterError,
    WhatsAppParsingError,
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
    """Test `deliver_media` raises MediaExtractionError if zip_path is missing."""
    with pytest.raises(MediaExtractionError):
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
