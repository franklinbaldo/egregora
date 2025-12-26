"""Tests for WhatsApp parser."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from egregora.input_adapters.whatsapp.exceptions import (
    DateParsingError,
    TimeParsingError,
)
from egregora.input_adapters.whatsapp.parsing import (
    WhatsAppExport,
    _parse_message_date,
    _parse_message_time,
    _parse_whatsapp_lines,
)


class TestWhatsAppParsing:
    """New tests for whatsapp parsing logic to raise exceptions on failure."""

    def test_parse_message_date_raises_error_on_invalid_date(self) -> None:
        """Verify _parse_message_date raises DateParsingError for invalid dates."""
        invalid_date_str = "not-a-date"
        with pytest.raises(DateParsingError, match=f"Failed to parse date string: '{invalid_date_str}'"):
            _parse_message_date(invalid_date_str)

    def test_parse_message_date_raises_error_on_empty_string(self) -> None:
        """Verify _parse_message_date raises DateParsingError with a custom message for an empty string."""
        with pytest.raises(DateParsingError, match="Date string is empty."):
            _parse_message_date("")

    def test_parse_message_time_raises_error_on_invalid_time(self) -> None:
        """Verify _parse_message_time raises TimeParsingError for invalid times."""
        invalid_time_str = "not-a-time"
        with pytest.raises(TimeParsingError, match=f"Failed to parse time string: '{invalid_time_str}'"):
            _parse_message_time(invalid_time_str)

    def test_parse_message_time_raises_error_on_empty_string(self) -> None:
        """Verify _parse_message_time raises TimeParsingError with a custom message for an empty string."""
        with pytest.raises(TimeParsingError, match="Time string is empty."):
            _parse_message_time("")

    def test_parse_whatsapp_lines_handles_invalid_line_gracefully(self, caplog: pytest.LogCaptureFixture) -> None:
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
