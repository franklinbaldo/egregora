"""Configuration for Pydantic AI backend switching.

This module provides environment-based feature flags to switch between
legacy google.genai implementations and new Pydantic AI implementations.

Environment Variables:
    EGREGORA_LLM_BACKEND: Global backend ("pydantic-ai" or "legacy")
    EGREGORA_WRITER_BACKEND: Writer agent backend
    EGREGORA_EDITOR_BACKEND: Editor agent backend
    EGREGORA_RANKING_BACKEND: Ranking agent backend

Precedence: Specific > Global > Default (pydantic-ai)

Example:
    # Use Pydantic AI for all agents (default)
    export EGREGORA_LLM_BACKEND=pydantic-ai

    # Use legacy for editor only
    export EGREGORA_EDITOR_BACKEND=legacy

    # Use legacy for all
    export EGREGORA_LLM_BACKEND=legacy

"""

import os
from typing import Literal

Backend = Literal["pydantic-ai", "legacy"]

# Default backend (after full migration, this will be "pydantic-ai")
DEFAULT_BACKEND: Backend = "pydantic-ai"


def get_backend(agent: Literal["writer", "editor", "ranking"]) -> Backend:
    """Get the backend to use for a specific agent.

    Args:
        agent: Agent name ("writer", "editor", or "ranking")

    Returns:
        Backend to use ("pydantic-ai" or "legacy")

    Example:
        >>> get_backend("writer")
        'pydantic-ai'
        >>> os.environ["EGREGORA_EDITOR_BACKEND"] = "legacy"
        >>> get_backend("editor")
        'legacy'

    """
    # Check agent-specific override
    agent_env = f"EGREGORA_{agent.upper()}_BACKEND"
    agent_backend = os.environ.get(agent_env)
    if agent_backend in ("pydantic-ai", "legacy"):
        return agent_backend  # type: ignore

    # Check global override
    global_backend = os.environ.get("EGREGORA_LLM_BACKEND")
    if global_backend in ("pydantic-ai", "legacy"):
        return global_backend  # type: ignore

    # Use default
    return DEFAULT_BACKEND


def use_pydantic_ai(agent: Literal["writer", "editor", "ranking"]) -> bool:
    """Check if Pydantic AI should be used for an agent.

    Args:
        agent: Agent name

    Returns:
        True if Pydantic AI should be used, False for legacy

    """
    return get_backend(agent) == "pydantic-ai"
