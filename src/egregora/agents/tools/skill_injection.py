"""Skill injection tool for dynamic agent capability extension.

This module enables agents to dynamically load and use skills at runtime by
spawning sub-agents with injected skill context. The parent agent only sees
the summary of the sub-agent's work, keeping context clean and focused.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from egregora.agents.tools.skill_loader import get_skill_loader

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


class SkillInjectionDeps(BaseModel):
    """Dependencies for skill injection tool.

    This should be provided in the agent's dependencies to enable skill injection.
    """

    model_config = {"arbitrary_types_allowed": True}

    parent_agent_model: Model = Field(..., description="Model to use for sub-agent")
    parent_agent_tools: list[Any] = Field(default_factory=list, description="Tools available to parent agent")
    parent_system_prompt: str = Field(default="", description="Parent agent's system prompt")
    skills_dir_override: str | None = Field(None, description="Optional override for skills directory")


async def use_skill(ctx: RunContext[SkillInjectionDeps], skill_name: str, task: str) -> str:
    """Load a skill and execute a task with it using a specialized sub-agent.

    This tool spawns a sub-agent with the requested skill content injected into
    its system prompt. The sub-agent can use all parent tools plus has access to
    `end_skill_use()` to signal completion. The parent agent only sees the
    summary of the sub-agent's work, keeping context clean.

    Args:
        ctx: Run context with parent agent configuration.
        skill_name: Name of the skill to use (e.g., "github-api", "pdf-analysis").
        task: Description of what to do with the skill.

    Returns:
        Summary of what the sub-agent accomplished.

    Examples:
        >>> await use_skill(ctx, "github-api", "Analyze PR #123 for security issues")
        >>> await use_skill(ctx, "data-analysis", "Generate statistics from conversation data")

    """
    logger.info(f"Loading skill: {skill_name} for task: {task[:100]}...")

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

    # Create sub-agent with skill context injected
    skill_system_prompt = _build_skill_system_prompt(
        parent_prompt=ctx.deps.parent_system_prompt,
        skill_content=skill_content.content,
        task=task,
    )

    # Create sub-agent with parent's model and tools + end_skill_use
    sub_agent = Agent(
        model=ctx.deps.parent_agent_model,
        system_prompt=skill_system_prompt,
        tools=[*ctx.deps.parent_agent_tools, end_skill_use],
        retries=2,  # Allow retries for transient failures
    )

    # Execute sub-agent
    try:
        summary = await _run_sub_agent(sub_agent, task, skill_name)
        logger.info(f"Skill usage completed: {skill_name} - {summary[:100]}...")
        return summary

    except Exception as e:
        error_msg = f"Sub-agent execution failed: {e}"
        logger.error(error_msg, exc_info=True)
        return f"ERROR: {error_msg}"


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
        >>> end_skill_use("Analyzed PR #123. Found 2 security issues: SQL injection in login.py and XSS in comments.js. Both are P0 severity.")
        >>> end_skill_use("Generated statistics: 1,234 messages from 15 authors over 30 days. Top topics: Python (45%), AI (30%), Remote work (25%).")

    """
    logger.debug(f"Sub-agent calling end_skill_use: {summary[:100]}...")
    return SkillCompletionResult(summary=summary)


def _build_skill_system_prompt(parent_prompt: str, skill_content: str, task: str) -> str:
    """Build system prompt for sub-agent with skill context.

    Args:
        parent_prompt: Parent agent's system prompt.
        skill_content: Skill instructions/content.
        task: Task description.

    Returns:
        Combined system prompt for sub-agent.

    """
    return f"""{parent_prompt}

# SKILL INJECTION MODE

You are currently in SKILL INJECTION MODE. You have been given a special skill
to help you complete a specific task.

## Injected Skill: {skill_content[:500]}...

{"...(skill content truncated)..." if len(skill_content) > 500 else ""}

## Your Task

{task}

## Important Instructions

1. Use the skill content above to complete the task
2. You have access to all your normal tools PLUS the skill's capabilities
3. When you're done, call the `end_skill_use(summary)` tool with a summary of what you accomplished
4. The summary should be concise (1-3 paragraphs) but capture key findings/results
5. Your parent agent will ONLY see the summary, so make it informative

## Full Skill Content

{skill_content}
"""


async def _run_sub_agent(agent: Agent[Any, Any], task: str, skill_name: str) -> str:
    """Run sub-agent and extract summary.

    The sub-agent can either:
    1. Call end_skill_use(summary) explicitly → returns that summary
    2. Finish naturally → uses final response as summary

    Args:
        agent: Sub-agent to run.
        task: Task prompt.
        skill_name: Name of skill being used (for logging).

    Returns:
        Summary of what was accomplished.

    Raises:
        RuntimeError: If execution fails.

    """
    result = await agent.run(task)

    # Check if the agent called end_skill_use by looking for the completion marker
    summary = _extract_summary_from_result(result)

    if _SKILL_COMPLETION_MARKER in summary:
        # Agent explicitly called end_skill_use
        # Extract the actual summary (remove marker)
        clean_summary = summary.replace(_SKILL_COMPLETION_MARKER, "").strip()
        logger.debug(f"Sub-agent used end_skill_use: {clean_summary[:100]}...")
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
    if hasattr(result, "data"):
        data = result.data
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
