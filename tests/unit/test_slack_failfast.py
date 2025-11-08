"""Unit tests for Slack adapter fail-fast behavior.

Tests:
- SlackInputSource.parse() raises NotImplementedError
- Error message is clear and helpful
"""

from pathlib import Path

import pytest

from egregora.ingestion.slack_input import SlackInputSource


def test_slack_parse_raises_not_implemented(tmp_path: Path):
    """SlackInputSource.parse() raises NotImplementedError (fail-fast)."""
    # Create mock Slack export directory
    slack_export = tmp_path / "slack-export"
    slack_export.mkdir()

    # Create channels.json and users.json (required by supports_format)
    (slack_export / "channels.json").write_text("[]")
    (slack_export / "users.json").write_text("[]")

    # Attempt to parse
    slack_input = SlackInputSource()

    with pytest.raises(NotImplementedError, match="Slack input source is not yet implemented"):
        slack_input.parse(slack_export)


def test_slack_error_message_helpful():
    """SlackInputSource error message explains what to do."""
    slack_input = SlackInputSource()

    with pytest.raises(
        NotImplementedError,
        match="only WhatsApp exports are supported",
    ):
        slack_input.parse(Path("/fake/path"))


def test_slack_supports_format_still_works(tmp_path: Path):
    """SlackInputSource.supports_format() still works (for future use)."""
    # Create mock Slack export directory
    slack_export = tmp_path / "slack-export"
    slack_export.mkdir()
    (slack_export / "channels.json").write_text("[]")
    (slack_export / "users.json").write_text("[]")

    slack_input = SlackInputSource()

    # should return True (format detection still works)
    assert slack_input.supports_format(slack_export)


def test_slack_source_type():
    """SlackInputSource.source_type returns 'slack'."""
    slack_input = SlackInputSource()
    assert slack_input.source_type == "slack"
