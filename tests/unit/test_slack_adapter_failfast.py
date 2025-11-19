"""Tests for the Slack adapter placeholder."""

from egregora.input_adapters.slack import SLACK_ADAPTER_PLACEHOLDER


def test_slack_placeholder_is_present():
    """Placeholder text should clearly state that Slack is disabled."""
    placeholder = SLACK_ADAPTER_PLACEHOLDER.lower()
    assert "disabled" in placeholder or "not registered" in placeholder
