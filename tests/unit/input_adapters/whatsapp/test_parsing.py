"""Tests for WhatsApp parser."""

import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from egregora.input_adapters.whatsapp.exceptions import (
    ChatEncodingError,
    DateParsingError,
    MalformedLineError,
    NoMessagesFoundError,
    TimeParsingError,
)
from egregora.input_adapters.whatsapp.parsing import (
    WhatsAppExport,
    ZipMessageSource,
    _parse_message_date,
    _parse_message_time,
    _parse_whatsapp_lines,
    parse_source,
)


@pytest.fixture
def whatsapp_export_with_malformed_line(tmp_path: Path) -> WhatsAppExport:
    """Creates a mock WhatsApp export ZIP with a malformed line."""
    zip_path = tmp_path / "whatsapp.zip"
    chat_file_name = "_chat.txt"
    chat_content = (
        "1/1/22, 12:00 - User 1: Hello\n"
        "99/99/99, 12:01 - User 2: This date is malformed\n"
        "1/1/22, 12:02 - User 3: World\n"
    )

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

    def test_parse_source_raises_error_when_no_messages_found(self, monkeypatch) -> None:
        """Verify parse_source raises NoMessagesFoundError when parsing yields no rows."""
        # 1. Arrange: Mock the internal parsing function to return an empty list
        monkeypatch.setattr(
            "egregora.input_adapters.whatsapp.parsing._parse_whatsapp_lines",
            lambda *args, **kwargs: [],
        )

        mock_export = WhatsAppExport(
            zip_path=Path("dummy.zip"),
            group_name="Test Group",
            group_slug="test-group",
            export_date=date(2023, 1, 1),
            chat_file="_chat.txt",
            media_files=[],
        )

        # 2. Act & Assert: Expect NoMessagesFoundError
        # The current implementation will return an empty Ibis table, causing the test to fail.
        with pytest.raises(NoMessagesFoundError, match=r"No messages found in 'dummy\.zip'"):
            parse_source(mock_export, timezone="UTC")

    def test_parse_message_date_raises_error_on_invalid_date(self) -> None:
        """Verify _parse_message_date raises DateParsingError for invalid dates."""
        invalid_date_str = "not-a-date"
        with pytest.raises(DateParsingError, match=f"Failed to parse date string: '{invalid_date_str}'"):
            _parse_message_date(invalid_date_str)

    def test_parse_message_date_raises_error_on_empty_string(self) -> None:
        """Verify _parse_message_date raises DateParsingError with a custom message for an empty string."""
        with pytest.raises(DateParsingError, match=r"Date string is empty\."):
            _parse_message_date("")

    def test_parse_message_time_raises_error_on_invalid_time(self) -> None:
        """Verify _parse_message_time raises TimeParsingError for invalid times."""
        invalid_time_str = "not-a-time"
        with pytest.raises(TimeParsingError, match=f"Failed to parse time string: '{invalid_time_str}'"):
            _parse_message_time(invalid_time_str)

    def test_parse_message_time_raises_error_on_empty_string(self) -> None:
        """Verify _parse_message_time raises TimeParsingError with a custom message for an empty string."""
        with pytest.raises(TimeParsingError, match=r"Time string is empty\."):
            _parse_message_time("")

    def test_parse_source_raises_error_on_empty_chat_log(
        self,
        whatsapp_export_with_empty_chat: WhatsAppExport,
    ) -> None:
        """
        Verify that parse_source raises NoMessagesFoundError for empty chat files.
        """
        with pytest.raises(NoMessagesFoundError):
            parse_source(export=whatsapp_export_with_empty_chat, timezone="UTC")

    def test_parse_whatsapp_lines_raises_malformed_line_error(self) -> None:
        """Verify _parse_whatsapp_lines raises MalformedLineError for lines with parsing errors."""
        # 1. Arrange: Create mock objects
        mock_export = WhatsAppExport(
            zip_path=Path("dummy.zip"),
            group_name="Test Group",
            group_slug="test-group",
            export_date=date(2023, 1, 1),
            chat_file="_chat.txt",
            media_files=[],
        )

        mock_source = MagicMock(spec=ZipMessageSource)
        malformed_line = "99/99/9999, 12:00 - Author: Message"
        mock_source.lines.return_value = iter([malformed_line])

        # 2. Act & Assert: Expect MalformedLineError
        with pytest.raises(MalformedLineError) as excinfo:
            _parse_whatsapp_lines(mock_source, mock_export, timezone="UTC")

        # 3. Assert exception context
        assert excinfo.value.line == malformed_line
        assert isinstance(excinfo.value.original_error, DateParsingError)

    def test_zipmessagesource_raises_chatencodingerror_on_unicode_decode_error(self, monkeypatch) -> None:
        """Verify ZipMessageSource raises ChatEncodingError on a UnicodeDecodeError."""
        # 1. Arrange
        mock_export = WhatsAppExport(
            zip_path=Path("dummy.zip"),
            group_name="Test Group",
            group_slug="test-group",
            export_date=date(2023, 1, 1),
            chat_file="_chat.txt",
            media_files=[],
        )
        decode_error = UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid start byte")

        # Mock the TextIOWrapper to simulate a decoding error
        mock_text_wrapper = MagicMock()
        mock_text_wrapper.__iter__.side_effect = decode_error
        monkeypatch.setattr(
            "egregora.input_adapters.whatsapp.parsing.io.TextIOWrapper", lambda *a, **kw: mock_text_wrapper
        )

        # Mock zipfile handling to avoid actual file operations
        mock_zip_instance = MagicMock()
        mock_zip_context = MagicMock()
        mock_zip_context.__enter__.return_value = mock_zip_instance
        monkeypatch.setattr("zipfile.ZipFile", lambda *a, **kw: mock_zip_context)

        # Mock validation functions so they don't interfere
        monkeypatch.setattr("egregora.input_adapters.whatsapp.parsing.validate_zip_contents", lambda zf: None)
        monkeypatch.setattr(
            "egregora.input_adapters.whatsapp.parsing.ensure_safe_member_size", lambda zf, member: None
        )

        source = ZipMessageSource(export=mock_export)

        # 2. Act & Assert
        with pytest.raises(ChatEncodingError) as excinfo:
            list(source.lines())

        # 3. Assert on the exception context
        assert excinfo.value.filename == mock_export.chat_file
        assert excinfo.value.original_error is decode_error
