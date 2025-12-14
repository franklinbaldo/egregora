"""Tests for /egregora command processing and announcement generation.

TDD: Write tests first, then implement functionality.
"""

import pytest

from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import DocumentType


class TestCommandDetection:
    """Test detection of /egregora commands in messages."""

    def test_detect_avatar_command(self):
        """Detect /egregora avatar command."""
        from egregora.agents.commands import is_command, parse_command

        message = "/egregora avatar set https://example.com/avatar.jpg"

        assert is_command(message)
        cmd = parse_command(message)
        assert cmd["type"] == "avatar"
        assert cmd["action"] == "set"
        assert "example.com/avatar.jpg" in cmd["params"]["url"]

    def test_detect_bio_command(self):
        """Detect /egregora bio command."""
        from egregora.agents.commands import is_command, parse_command

        message = "/egregora bio I am an AI researcher"

        assert is_command(message)
        cmd = parse_command(message)
        assert cmd["type"] == "bio"
        assert "AI researcher" in cmd["params"]["bio"]

    def test_detect_interests_command(self):
        """Detect /egregora interests command."""
        from egregora.agents.commands import is_command, parse_command

        message = "/egregora interests AI, machine learning, ethics"

        assert is_command(message)
        cmd = parse_command(message)
        assert cmd["type"] == "interests"
        assert "AI" in cmd["params"]["interests"]

    def test_not_command(self):
        """Regular message is not a command."""
        from egregora.agents.commands import is_command

        message = "This is a regular message about egregora"
        assert not is_command(message)

    def test_case_insensitive(self):
        """Commands are case-insensitive."""
        from egregora.agents.commands import is_command

        assert is_command("/EGREGORA avatar set url")
        assert is_command("/Egregora bio text")


class TestCommandFiltering:
    """Test filtering commands from LLM input."""

    def test_filter_commands_from_messages(self):
        """Commands should be filtered out before sending to LLM."""
        from egregora.agents.commands import filter_commands

        messages = [
            {"text": "Regular message 1", "author": "john"},
            {"text": "/egregora avatar set https://...", "author": "alice"},
            {"text": "Regular message 2", "author": "bob"},
            {"text": "/egregora bio I am a researcher", "author": "alice"},
            {"text": "Regular message 3", "author": "john"},
        ]

        filtered = filter_commands(messages)

        # Only 3 regular messages should remain
        assert len(filtered) == 3
        assert all("/egregora" not in m["text"].lower() for m in filtered)

    def test_extract_commands(self):
        """Extract only command messages."""
        from egregora.agents.commands import extract_commands

        messages = [
            {"text": "Regular message", "author": "john"},
            {"text": "/egregora avatar set url", "author": "alice"},
            {"text": "/egregora bio text", "author": "bob"},
        ]

        commands = extract_commands(messages)

        assert len(commands) == 2
        assert all("/egregora" in m["text"].lower() for m in commands)


class TestAnnouncementGeneration:
    """Test ANNOUNCEMENT document generation from commands."""

    def test_avatar_command_creates_announcement(self):
        """Avatar command → ANNOUNCEMENT document."""
        from egregora.agents.commands import command_to_announcement

        message = {
            "text": "/egregora avatar set https://example.com/avatar.jpg",
            "author_uuid": "john-uuid",
            "author_name": "John Doe",
            "timestamp": "2025-03-07T10:00:00",
        }

        doc = command_to_announcement(message)

        assert doc.type == DocumentType.ANNOUNCEMENT
        assert doc.metadata["authors"][0]["uuid"] == EGREGORA_UUID
        assert doc.metadata["event_type"] == "avatar_update"
        assert doc.metadata["actor"] == "john-uuid"
        assert "John Doe" in doc.content
        assert "avatar" in doc.content.lower()

    def test_bio_command_creates_announcement(self):
        """Bio command → ANNOUNCEMENT document."""
        from egregora.agents.commands import command_to_announcement

        message = {
            "text": "/egregora bio I am an AI researcher",
            "author_uuid": "alice-uuid",
            "author_name": "Alice",
            "timestamp": "2025-03-07T11:00:00",
        }

        doc = command_to_announcement(message)

        assert doc.type == DocumentType.ANNOUNCEMENT
        assert doc.metadata["event_type"] == "bio_update"
        assert doc.metadata["actor"] == "alice-uuid"
        assert "AI researcher" in doc.content

    def test_interests_command_creates_announcement(self):
        """Interests command → ANNOUNCEMENT document."""
        from egregora.agents.commands import command_to_announcement

        message = {
            "text": "/egregora interests AI, ethics, philosophy",
            "author_uuid": "bob-uuid",
            "author_name": "Bob",
            "timestamp": "2025-03-07T12:00:00",
        }

        doc = command_to_announcement(message)

        assert doc.type == DocumentType.ANNOUNCEMENT
        assert doc.metadata["event_type"] == "interests_update"
        assert "AI" in doc.content
        assert "ethics" in doc.content

    def test_announcement_metadata_structure(self):
        """Verify ANNOUNCEMENT metadata is correctly structured."""
        from egregora.agents.commands import command_to_announcement

        message = {
            "text": "/egregora avatar set url",
            "author_uuid": "test-uuid",
            "author_name": "Test User",
            "timestamp": "2025-03-07T10:00:00",
        }

        doc = command_to_announcement(message)

        # Verify required metadata
        assert "title" in doc.metadata
        assert "authors" in doc.metadata
        assert "event_type" in doc.metadata
        assert "actor" in doc.metadata
        assert "date" in doc.metadata

        # Verify Egregora authorship
        assert doc.metadata["authors"][0]["uuid"] == EGREGORA_UUID
        assert doc.metadata["authors"][0]["name"] == EGREGORA_NAME


class TestCommandPipeline:
    """Integration tests for command processing in pipeline."""

    def test_commands_not_sent_to_writer(self):
        """Commands filtered before WriterWorker receives messages."""
        from egregora.agents.commands import filter_commands

        messages = [
            {"text": "Interesting AI discussion", "author": "john"},
            {"text": "/egregora avatar set url", "author": "alice"},
            {"text": "I agree with that point", "author": "bob"},
        ]

        # Simulate pipeline filtering
        clean_messages = filter_commands(messages)

        # WriterWorker should only see non-command messages
        assert len(clean_messages) == 2
        assert clean_messages[0]["text"] == "Interesting AI discussion"
        assert clean_messages[1]["text"] == "I agree with that point"

    def test_commands_generate_announcements(self):
        """Commands generate ANNOUNCEMENT documents in pipeline."""
        from egregora.agents.commands import command_to_announcement, extract_commands

        messages = [
            {
                "text": "Regular",
                "author": "john",
                "author_uuid": "j",
                "author_name": "John",
                "timestamp": "2025-03-07",
            },
            {
                "text": "/egregora avatar set url",
                "author": "alice",
                "author_uuid": "a",
                "author_name": "Alice",
                "timestamp": "2025-03-07",
            },
        ]

        # Extract commands
        commands = extract_commands(messages)

        # Generate announcements
        announcements = [command_to_announcement(cmd) for cmd in commands]

        assert len(announcements) == 1
        assert announcements[0].type == DocumentType.ANNOUNCEMENT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
