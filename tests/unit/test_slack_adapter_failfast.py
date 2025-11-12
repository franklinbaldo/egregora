"""Unit tests for SlackAdapter fail-fast behavior.

Tests that the SlackAdapter (from adapters/slack.py) fails fast
with NotImplementedError when called.
"""

from pathlib import Path

import pytest

from egregora.input_adapters.slack import SlackAdapter


def test_slack_adapter_parse_raises_not_implemented(tmp_path: Path):
    """SlackAdapter.parse() raises NotImplementedError immediately."""
    # Create mock file
    slack_file = tmp_path / "slack.json"
    slack_file.write_text("{}")

    adapter = SlackAdapter()

    with pytest.raises(NotImplementedError, match="Slack adapter is not yet implemented"):
        adapter.parse(slack_file)


def test_slack_adapter_extract_media_raises(tmp_path: Path):
    """SlackAdapter.extract_media() raises NotImplementedError."""
    adapter = SlackAdapter()

    with pytest.raises(NotImplementedError, match="media extraction is not yet implemented"):
        adapter.extract_media(tmp_path, tmp_path)


def test_slack_adapter_get_metadata_raises(tmp_path: Path):
    """SlackAdapter.get_metadata() raises NotImplementedError."""
    adapter = SlackAdapter()

    with pytest.raises(NotImplementedError, match="metadata extraction is not yet implemented"):
        adapter.get_metadata(tmp_path)


def test_slack_adapter_source_properties():
    """SlackAdapter source properties are set correctly."""
    adapter = SlackAdapter()

    assert adapter.source_name == "Slack"
    assert adapter.source_identifier == "slack"
