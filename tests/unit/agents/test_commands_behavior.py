"""Behavioral tests for system command processing.

Verifies the behavior of command parsing, filtering, and document generation.
"""

from unittest.mock import patch

import pytest

from egregora.agents.commands import (
    command_to_announcement,
    extract_commands,
    filter_commands,
    is_command,
    parse_command,
)
from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import DocumentType


class TestIsCommand:
    """Behavioral tests for is_command()."""

    def test_identifies_commands_case_insensitive(self):
        """Given a string starting with /egregora (any case), it returns True."""
        assert is_command("/egregora") is True
        assert is_command("/EGREGORA") is True
        assert is_command("/Egregora") is True
        assert is_command("/egregora command") is True

    def test_identifies_non_commands(self):
        """Given a string NOT starting with /egregora, it returns False."""
        assert is_command("hello world") is False
        assert is_command("/other command") is False
        assert is_command("prefix /egregora") is False

    def test_handles_whitespace(self):
        """Given strings with leading/trailing whitespace, it handles them correctly."""
        assert is_command("  /egregora  ") is True
        assert is_command("   hello   ") is False

    def test_handles_empty_input(self):
        """Given empty strings, it returns False."""
        assert is_command("") is False
        assert is_command("   ") is False


class TestParseCommand:
    """Behavioral tests for parse_command()."""

    def test_parses_avatar_command(self):
        """Given an avatar command, it parses action and url."""
        text = "/egregora avatar set https://example.com/img.jpg"
        result = parse_command(text)
        assert result["type"] == "avatar"
        assert result["action"] == "set"
        assert result["params"]["url"] == "https://example.com/img.jpg"

    def test_parses_bio_command(self):
        """Given a bio command, it parses the bio text."""
        text = "/egregora bio I am a researcher."
        result = parse_command(text)
        assert result["type"] == "bio"
        assert result["action"] == "update"
        assert result["params"]["bio"] == "I am a researcher."

    def test_parses_interests_command(self):
        """Given an interests command, it parses the list."""
        text = "/egregora interests coding, music, art"
        result = parse_command(text)
        assert result["type"] == "interests"
        assert result["action"] == "update"
        assert result["params"]["interests"] == "coding, music, art"

    def test_parses_unknown_command(self):
        """Given an unknown command type, it returns type=unknown_cmd and raw params."""
        text = "/egregora magic do something"
        result = parse_command(text)
        assert result["type"] == "magic"
        assert result["action"] == "unknown"
        assert result["params"]["raw"] == "do something"

    def test_handles_empty_command_with_space(self):
        """Given the prefix with space, it returns unknown type."""
        # Note: Implementation strips trailing space before regex, so it behaves like bare prefix
        text = "/egregora "
        result = parse_command(text)
        assert result["type"] == "/egregora"

    def test_handles_bare_prefix(self):
        """Given just the prefix without space, it treats prefix as command type."""
        # This reflects current implementation behavior where /egregora is not stripped
        # if not followed by whitespace.
        text = "/egregora"
        result = parse_command(text)
        assert result["type"] == "/egregora"

    def test_handles_empty_input_string(self):
        """Given empty string to parse_command, it returns unknown/unknown."""
        # This hits the 'if not parts' branch
        result = parse_command("")
        assert result["type"] == "unknown"
        assert result["action"] == "unknown"


class TestFilterAndExtractCommands:
    """Behavioral tests for filtering and extraction functions."""

    @pytest.fixture
    def mixed_messages(self):
        return [
            {"text": "Hello world", "id": 1},
            {"text": "/egregora bio test", "id": 2},
            {"text": "Another message", "id": 3},
            {"text": "/EGREGORA avatar set url", "id": 4},
        ]

    def test_filter_commands_removes_commands(self, mixed_messages):
        """Given a list of mixed messages, filter_commands returns only non-commands."""
        result = filter_commands(mixed_messages)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 3

    def test_extract_commands_returns_only_commands(self, mixed_messages):
        """Given a list of mixed messages, extract_commands returns only commands."""
        result = extract_commands(mixed_messages)
        assert len(result) == 2
        assert result[0]["id"] == 2
        assert result[1]["id"] == 4

    def test_handles_missing_text_field(self):
        """Given messages without text field, they are treated as non-commands."""
        messages = [{"other": "field"}]
        assert len(filter_commands(messages)) == 1
        assert len(extract_commands(messages)) == 0


class TestCommandToAnnouncement:
    """Behavioral tests for command_to_announcement()."""

    @pytest.fixture
    def base_message(self):
        return {
            "author_uuid": "user-123",
            "author_name": "Test User",
            "timestamp": "2023-10-27T10:00:00Z",
        }

    def test_creates_avatar_announcement(self, base_message):
        """Given an avatar command, creates correct ANNOUNCEMENT document."""
        message = base_message | {"text": "/egregora avatar set https://example.com/img.jpg"}

        doc = command_to_announcement(message)

        assert doc.type == DocumentType.ANNOUNCEMENT
        assert doc.metadata["title"] == "Test User Updated Avatar"
        assert doc.metadata["event_type"] == "avatar_update"
        assert doc.metadata["actor"] == "user-123"
        assert doc.metadata["subject"] == "user-123"
        assert "updated their avatar" in doc.content
        assert doc.metadata["authors"] == [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}]

    def test_creates_bio_announcement(self, base_message):
        """Given a bio command, creates correct ANNOUNCEMENT document."""
        message = base_message | {"text": "/egregora bio My new bio"}

        doc = command_to_announcement(message)

        assert doc.metadata["title"] == "Test User Updated Bio"
        assert doc.metadata["event_type"] == "bio_update"
        assert "My new bio" in doc.content

    def test_creates_interests_announcement(self, base_message):
        """Given an interests command, creates correct ANNOUNCEMENT document."""
        message = base_message | {"text": "/egregora interests A, B, C"}

        doc = command_to_announcement(message)

        assert doc.metadata["title"] == "Test User Updated Interests"
        assert doc.metadata["event_type"] == "interests_update"
        assert "A, B, C" in doc.content

    def test_creates_generic_system_event(self, base_message):
        """Given an unknown command, creates generic system event."""
        message = base_message | {"text": "/egregora unknown-cmd params"}

        doc = command_to_announcement(message)

        assert "System Event" in doc.metadata["title"]
        assert doc.metadata["event_type"] == "system_event"
        assert "unknown-cmd" in doc.content

    def test_handles_timestamp_variants(self, base_message):
        """Given different timestamp formats, parses date correctly."""
        # ISO format
        msg1 = base_message | {"text": "/egregora bio test", "timestamp": "2023-10-27T10:00:00Z"}
        doc1 = command_to_announcement(msg1)
        assert doc1.metadata["date"] == "2023-10-27"

        # Simple string fallback
        msg2 = base_message | {"text": "/egregora bio test", "timestamp": "2023-10-28"}
        doc2 = command_to_announcement(msg2)
        assert doc2.metadata["date"] == "2023-10-28"

    def test_handles_malformed_string_timestamp(self, base_message):
        """Given invalid timestamp string, falls back to splitting by 'T'."""
        # This behavior is risky but reflects current implementation
        message = base_message | {"text": "/egregora bio test", "timestamp": "invalid-date-format"}

        # We don't need to mock datetime here because fromisoformat will raise ValueError naturally
        # for this input, and the code catches it and does .split("T")[0]

        doc = command_to_announcement(message)
        assert doc.metadata["date"] == "invalid-date-format"

    def test_handles_non_string_timestamp(self, base_message):
        """Given non-string timestamp, defaults to current date."""
        message = base_message | {"text": "/egregora bio test", "timestamp": 12345}

        with patch("egregora.agents.commands.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value.isoformat.return_value = "2025-01-01"

            doc = command_to_announcement(message)
            assert doc.metadata["date"] == "2025-01-01"
