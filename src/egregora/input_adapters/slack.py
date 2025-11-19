"""Placeholder module for the Slack input adapter.

The Slack adapter has been disabled and is not registered as a built-in
input adapter. This placeholder keeps the module path available while
clearly signaling that Slack exports are not supported. To add Slack
support, implement a full adapter in a third-party plugin and register it
via the ``egregora.adapters`` entry-point group.
"""

from __future__ import annotations

SLACK_ADAPTER_PLACEHOLDER = (
    "Slack input adapter is disabled and not registered. "
    "Provide a third-party adapter plugin to enable Slack export support."
)

__all__ = ["SLACK_ADAPTER_PLACEHOLDER"]
