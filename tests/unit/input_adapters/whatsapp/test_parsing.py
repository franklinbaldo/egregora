"""Tests for WhatsApp parser."""
import zipfile
from datetime import date
from pathlib import Path

import pytest

from egregora.input_adapters.whatsapp.exceptions import (
    DateParsingError,
    EmptyChatLogError,
    TimeParsingError,
    WhatsAppParsingError,
)
from egregora.input_adapters.whatsapp.parsing import (
    WhatsAppExport,
    _parse_message_date,
    _parse_message_time,
    parse_source,
)


@pytest.fixture
def whatsapp_export_with_malformed_line(tmp_path: Path) -> WhatsAppExport:
    """Creates a mock WhatsApp export ZIP with a malformed line."""
    zip_path = tmp_path / "whatsapp.zip"
    chat_file_name = "_chat.txt"
    chat_content = "1/1/22, 12:00 - User 1: Hello\n" "99/99/99, 12:01 - User 2: This date is malformed\n" "1/1/22, 12:02 - User 3: World\n"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(chat_file_name, chat_content)

    return WhatsAppExport(
        zip_path=zip_path,
        group_name="Test Group",
        group_slug="test-group",
        export_date=date(2022, 1, 1),
        chat_file=chat_file_name,
        media_files=[],
    )


@pytest.fixture
def whatsapp_export_with_empty_chat(tmp_path: Path) -> WhatsAppExport:
    """Creates a mock WhatsApp export ZIP with an empty chat file."""
    zip_path = tmp_path / "whatsapp_empty.zip"
    chat_file_name = "_chat.txt"
    chat_content = ""  # Empty content

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(chat_file_name, chat_content)

    return WhatsAppExport(
        zip_path=zip_path,
        group_name="Test Group Empty",
        group_slug="test-group-empty",
        export_date=date(2022, 1, 1),
        chat_file=chat_file_name,
        media_files=[],
    )


class TestWhatsAppParsing:
    """New tests for whatsapp parsing logic to raise exceptions on failure."""

    def test_parse_message_date_raises_error_on_invalid_date(self) -> None:
        """Verify _parse_message_date raises DateParsingError for invalid dates."""
        invalid_date_str = "not-a-date"
        with pytest.raises(DateParsingError, match=f"Failed to parse date string: '{invalid_date_str}'"):
            _parse_message_date(invalid_date_str)

    def test_parse_message_time_raises_error_on_invalid_time(self) -> None:
        """Verify _parse_message_time raises TimeParsingError for invalid times."""
        invalid_time_str = "not-a-time"
        with pytest.raises(TimeParsingError, match=f"Failed to parse time string: '{invalid_time_str}'"):
            _parse_message_time(invalid_time_str)

    def test_parse_source_raises_error_on_malformed_line(
        self,
        whatsapp_export_with_malformed_line: WhatsAppExport,
    ) -> None:
        """
        Verify that parse_source raises WhatsAppParsingError when a line is malformed
        instead of silently continuing.
        """
        with pytest.raises(WhatsAppParsingError):
            parse_source(export=whatsapp_export_with_malformed_line, timezone="UTC")

    def test_parse_source_raises_error_on_empty_chat_log(
        self,
        whatsapp_export_with_empty_chat: WhatsAppExport,
    ) -> None:
        """
        Verify that parse_source raises EmptyChatLogError for empty chat files.
        """
        with pytest.raises(EmptyChatLogError):
            parse_source(export=whatsapp_export_with_empty_chat, timezone="UTC")
