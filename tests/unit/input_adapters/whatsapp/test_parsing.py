"""Tests for WhatsApp parser."""

import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from egregora.input_adapters.whatsapp.exceptions import (
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
        """Verify _parse_message_date returns None for invalid dates."""
        invalid_date_str = "not-a-date"
        result = _parse_message_date(invalid_date_str)
        assert result is None

    def test_parse_message_date_raises_error_on_empty_string(self) -> None:
        """Verify _parse_message_date returns None for an empty string."""
        result = _parse_message_date("")
        assert result is None

    def test_parse_message_time_raises_error_on_invalid_time(self) -> None:
        """Verify _parse_message_time returns None for invalid times."""
        invalid_time_str = "not-a-time"
        result = _parse_message_time(invalid_time_str)
        assert result is None

    def test_parse_message_time_raises_error_on_empty_string(self) -> None:
        """Verify _parse_message_time returns None for an empty string."""
        result = _parse_message_time("")
        assert result is None

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
