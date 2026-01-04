"""Agent-related classes and functions."""
from .registry import AgentResolver, ToolRegistry

# Egregora system author constants
# Used when Egregora generates content (PROFILE posts, ANNOUNCEMENT posts)
EGREGORA_UUID = "00000000-0000-0000-0000-000000000000"
EGREGORA_NAME = "Egregora"

__all__ = ["AgentResolver", "ToolRegistry", "EGREGORA_UUID", "EGREGORA_NAME"]
