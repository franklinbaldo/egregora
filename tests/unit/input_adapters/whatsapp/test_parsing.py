"""Tests for WhatsApp parser."""

import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from egregora.input_adapters.whatsapp.exceptions import (
    DateParsingError,
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

    def test_parse_whatsapp_lines_handles_malformed_lines_gracefully(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify _parse_whatsapp_lines treats malformed lines as continuations (resilient behavior)."""
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
        # This line is intentionally malformed - it will be treated as a continuation line
        mock_source.lines.return_value = iter(["99/99/9999, 12:00 - Author: Message"])

        # 2. Act: Parse the lines - should not raise an exception
        rows = _parse_whatsapp_lines(mock_source, mock_export, timezone="UTC")

        # 3. Assert: Returns empty list since there's no valid starting message
        assert rows == []
        # Should log a warning about the unparseable timestamp
        assert "Could not parse timestamp, treating as continuation" in caplog.text

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

    def test_parse_whatsapp_lines_handles_invalid_line_gracefully(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify _parse_whatsapp_lines handles invalid lines by logging and continuing."""
        # Arrange
        mock_export = MagicMock(spec=WhatsAppExport)
        mock_export.group_slug = "test-group"
        mock_export.export_date = date(2023, 1, 1)

        mock_source = MagicMock()
        invalid_line = "99/99/99, 99:99 - Author: Invalid Message"
        valid_line = "01/01/23, 12:00 - Author: Valid Message"
        mock_source.lines.return_value = [valid_line, invalid_line]

        # Act
        rows = _parse_whatsapp_lines(mock_source, mock_export, "UTC")

        # Assert
        assert len(rows) == 1
        assert "Valid Message\n99/99/99, 99:99 - Author: Invalid Message" in rows[0]["text"]
        assert "Could not parse timestamp, treating as continuation" in caplog.text

    def test_parse_source_raises_error_on_empty_chat_log(
        self,
        whatsapp_export_with_empty_chat: WhatsAppExport,
    ) -> None:
        """
        Verify that parse_source raises NoMessagesFoundError for empty chat files.
        """
        with pytest.raises(NoMessagesFoundError):
            parse_source(export=whatsapp_export_with_empty_chat, timezone="UTC")
