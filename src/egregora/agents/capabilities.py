"""Agent capabilities for the Writer agent.

This module provides capability objects that configure the writer agent's
behavior and available tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass
class AgentCapability:
    """Base class for agent capabilities."""


@dataclass
class RagCapability(AgentCapability):
    """Enable RAG (Retrieval Augmented Generation) capability."""


@dataclass
class BannerCapability(AgentCapability):
    """Enable banner generation capability."""


@dataclass
class BackgroundBannerCapability(AgentCapability):
    """Enable background banner generation capability."""

    run_id: UUID
