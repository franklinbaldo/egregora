"""Skill injection tool for dynamic agent capability extension.

This module enables agents to dynamically load and use skills at runtime by
spawning sub-agents with injected skill context. The parent agent only sees
the summary of the sub-agent's work, keeping context clean and focused.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from egregora.agents.tools.skill_loader import get_skill_loader
from egregora.resources.prompts import render_prompt

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)


# Marker for detecting when sub-agent calls end_skill_use
_SKILL_COMPLETION_MARKER = "<<<SKILL_EXECUTION_COMPLETED>>>"


class SkillCompletionResult(BaseModel):
    """Result returned by end_skill_use tool."""

    summary: str = Field(..., description="Summary of what was accomplished")
    marker: str = Field(
        default=_SKILL_COMPLETION_MARKER,
        description="Internal completion marker",
        exclude=True,  # Don't include in serialization
    )


@runtime_checkable
class SkillInjectionSupport(Protocol):
    """Protocol for agent dependencies that support skill injection.

    Parent agents that want to support skill injection should have their deps
    implement this protocol by providing these attributes.
    """

    @property
    def agent_model(self) -> Model:
        """The model used by this agent."""
        ...

    @property
    def agent_tools(self) -> list[Any]:
        """Tools available to this agent (excluding use_skill itself)."""
        ...

    @property
    def agent_system_prompt(self) -> str:
        """System prompt for this agent."""
        ...


def use_skill(ctx: RunContext[Any], skill_name: str, task: str) -> str:
    """Load a skill and execute a task with it using a specialized sub-agent.

    This tool spawns a sub-agent with the requested skill content injected into
    its system prompt. The sub-agent inherits the parent's model, tools, AND
    dependencies, ensuring parent tools work correctly (accessing storage, RAG, etc.).

    The parent agent only sees the summary of the sub-agent's work, keeping
    context clean.

    Args:
        ctx: Run context from parent agent. Parent deps must implement
             SkillInjectionSupport protocol (agent_model, agent_tools,
             agent_system_prompt properties).
        skill_name: Name of the skill to use (e.g., "github-api", "pdf-analysis").
        task: Description of what to do with the skill.

    Returns:
        Summary of what the sub-agent accomplished.

    Examples:
        >>> use_skill(ctx, "github-api", "Analyze PR #123 for security issues")
        >>> use_skill(ctx, "data-analysis", "Generate statistics from conversation data")

    """
    logger.info("Loading skill: %s for task: %s...", skill_name, task[:100])

    # Check if parent deps supports skill injection
    if not isinstance(ctx.deps, SkillInjectionSupport):
        error_msg = (
            "Parent agent deps must implement SkillInjectionSupport protocol "
            "(provide agent_model, agent_tools, agent_system_prompt properties)"
        )
        logger.exception(error_msg)
        return f"ERROR: {error_msg}"

    # Load skill content
    skill_loader = get_skill_loader()
    try:
        skill_content = skill_loader.load_skill(skill_name)
    except FileNotFoundError:
        available = skill_loader.list_available_skills()
        error_msg = (
            f"Skill '{skill_name}' not found. "
            f"Available skills: {', '.join(available) if available else 'none'}"
        )
        logger.exception(error_msg)
        return f"ERROR: {error_msg}"

    truncate_limit = 500
    truncated = len(skill_content.content) > truncate_limit

    skill_system_prompt = render_prompt(
        "skill_injection.jinja",
        parent_prompt=ctx.deps.agent_system_prompt,
        skill_content=skill_content.content,
        skill_content_truncated=skill_content.content[:truncate_limit],
        truncated=truncated,
        task=task,
    )

    # Create sub-agent with parent's model and tools + end_skill_use
    # IMPORTANT: Sub-agent will receive parent's deps when we call run()
    sub_agent = Agent(
        model=ctx.deps.agent_model,
        system_prompt=skill_system_prompt,
        tools=[*ctx.deps.agent_tools, end_skill_use],
        retries=2,  # Allow retries for transient failures
    )

    # Execute sub-agent with parent's dependencies
    # This ensures parent tools work correctly (can access storage, RAG, etc.)
    try:
        summary = _run_sub_agent(sub_agent, task, skill_name, ctx.deps)
    except Exception as e:
        error_msg = f"Sub-agent execution failed: {e}"
        logger.error(error_msg, exc_info=True)
        return f"ERROR: {error_msg}"

    logger.info("Skill usage completed: %s - %s...", skill_name, summary[:100])
    return summary


def end_skill_use(summary: str) -> SkillCompletionResult:
    """Signal completion of skill usage and return to parent agent.

    This tool is ONLY available to sub-agents spawned by use_skill().
    When called, it signals that the sub-agent has completed its task
    and provides a summary to return to the parent agent.

    Args:
        summary: Summary of what was accomplished with the skill.
            Should be concise but informative (1-3 paragraphs).
            Include key findings, results, or actions taken.

    Returns:
        SkillCompletionResult with summary and completion marker.

    Examples:
        >>> end_skill_use("Analyzed PR #123. Found 2 security issues: SQL injection and XSS.")
        >>> end_skill_use("Stats: 1,234 messages from 15 authors. Top: Python (45%), AI (30%).")

    """
    logger.debug("Sub-agent calling end_skill_use: %s...", summary[:100])
    return SkillCompletionResult(summary=summary)


# _build_skill_system_prompt removed in favor of Jinja template


def _run_sub_agent(agent: Agent[Any, Any], task: str, skill_name: str, parent_deps: Any) -> str:
    """Run sub-agent and extract summary.

    The sub-agent can either:
    1. Call end_skill_use(summary) explicitly → returns that summary
    2. Finish naturally → uses final response as summary

    Args:
        agent: Sub-agent to run.
        task: Task prompt.
        skill_name: Name of skill being used (for logging).
        parent_deps: Parent agent's dependencies to pass to sub-agent.
                     This ensures tools can access storage, RAG, etc.

    Returns:
        Summary of what was accomplished.

    Raises:
        RuntimeError: If execution fails.

    """
    # Run sub-agent with parent's dependencies
    # This is CRITICAL: parent tools need access to parent's storage, RAG, etc.
    result = agent.run_sync(task, deps=parent_deps)

    # Check if the agent called end_skill_use by looking for the completion marker
    summary = _extract_summary_from_result(result)

    if _SKILL_COMPLETION_MARKER in summary:
        # Agent explicitly called end_skill_use
        # Extract the actual summary (remove marker)
        clean_summary = summary.replace(_SKILL_COMPLETION_MARKER, "").strip()
        logger.debug("Sub-agent used end_skill_use: %s...", clean_summary[:100])
        return clean_summary
    # Agent finished naturally without calling end_skill_use
    logger.debug("Sub-agent finished without end_skill_use, using final response as summary")
    return summary


def _extract_summary_from_result(result: Any) -> str:
    """Extract summary text from agent result.

    Handles different result types from pydantic-ai agents.

    Args:
        result: Agent run result.

    Returns:
        Summary text.

    """
    # Try to get data from result
    if hasattr(result, "output"):
        data = result.output
        # If data is SkillCompletionResult, extract summary
        if isinstance(data, SkillCompletionResult):
            return f"{_SKILL_COMPLETION_MARKER}\n{data.summary}"
        # If data is a dict with summary key
        if isinstance(data, dict) and "summary" in data:
            return str(data["summary"])
        # Otherwise convert to string
        return str(data)

    # Fallback: convert entire result to string
    return str(result)
