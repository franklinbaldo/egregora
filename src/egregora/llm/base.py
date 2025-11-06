"""Base infrastructure for creating standardized Pydantic AI agents.

This module provides factory functions that ensure all Egregora agents follow
consistent patterns for observability, error handling, and testing.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic_ai import Agent

try:
    from pydantic_ai.models.gemini import GeminiModel
except ImportError:  # pragma: no cover - newer SDK uses google module
    from pydantic_ai.models.google import GoogleModel as GeminiModel  # type: ignore

from egregora.utils.logfire_config import configure_logfire

logger = logging.getLogger(__name__)

# Type variables for agent state and result types
TDeps = TypeVar("TDeps")
TResult = TypeVar("TResult")


def create_agent[TDeps](
    model_name: str,
    *,
    system_prompt: str,
    deps_type: type[TDeps],
    agent_model: Any | None = None,
    enable_logfire: bool = True,
) -> Agent[TDeps, str]:
    """Create a text-output Pydantic AI agent with standard Egregora configuration.

    This factory ensures all agents have:
    - Logfire observability (when enabled)
    - Consistent model initialization
    - Test model injection support
    - Standard error handling

    Args:
        model_name: Gemini model name (e.g., "models/gemini-2.0-flash-exp")
        system_prompt: System prompt for the agent
        deps_type: Type for agent state/dependencies
        agent_model: Optional test model for deterministic tests
        enable_logfire: Whether to enable Logfire observability

    Returns:
        Configured Pydantic AI agent with text output

    Example:
        >>> from dataclasses import dataclass
        >>> @dataclass
        >>> class MyAgentState:
        ...     data: str
        >>> agent = create_agent(
        ...     "models/gemini-flash-latest",
        ...     system_prompt="You are a helpful assistant",
        ...     deps_type=MyAgentState,
        ... )

    """
    if enable_logfire:
        configure_logfire()
        logger.debug("Logfire configured for agent %s", model_name)

    model = agent_model or GeminiModel(model_name)

    return Agent[TDeps, str](
        model=model,
        system_prompt=system_prompt,
        deps_type=deps_type,
    )


def create_agent_with_result_type[TDeps, TResult](  # noqa: PLR0913
    model_name: str,
    *,
    system_prompt: str,
    deps_type: type[TDeps],
    result_type: type[TResult],
    agent_model: Any | None = None,
    enable_logfire: bool = True,
) -> Agent[TDeps, TResult]:
    """Create a structured-output Pydantic AI agent with standard Egregora configuration.

    Similar to create_agent() but for agents that return structured data via Pydantic models.
    The agent will use tool calling to return typed results.

    Args:
        model_name: Gemini model name (e.g., "models/gemini-2.0-flash-exp")
        system_prompt: System prompt for the agent
        deps_type: Type for agent state/dependencies
        result_type: Pydantic model type for structured output
        agent_model: Optional test model for deterministic tests
        enable_logfire: Whether to enable Logfire observability

    Returns:
        Configured Pydantic AI agent with structured output

    Example:
        >>> from pydantic import BaseModel
        >>> class Summary(BaseModel):
        ...     title: str
        ...     content: str
        >>> agent = create_agent_with_result_type(
        ...     "models/gemini-flash-latest",
        ...     system_prompt="Summarize the input",
        ...     deps_type=MyAgentState,
        ...     result_type=Summary,
        ... )

    """
    if enable_logfire:
        configure_logfire()
        logger.debug("Logfire configured for agent %s with result type %s", model_name, result_type)

    model = agent_model or GeminiModel(model_name)

    return Agent[TDeps, TResult](
        model=model,
        system_prompt=system_prompt,
        deps_type=deps_type,
        result_type=result_type,
    )
