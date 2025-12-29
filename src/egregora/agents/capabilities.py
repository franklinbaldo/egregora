"""Defines the capabilities that can be dynamically added to an agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.agents.types import RunId


class AgentCapability:
    """Base class for agent capabilities."""


class RagCapability(AgentCapability):
    """Capability for Retrieval-Augmented Generation."""


class BannerCapability(AgentCapability):
    """Capability for generating banners synchronously."""


class BackgroundBannerCapability(AgentCapability):
    """Capability for generating banners in the background."""

    def __init__(self, run_id: RunId) -> None:
        self.run_id = run_id
