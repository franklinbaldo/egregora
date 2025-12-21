"""Pydantic-AI powered writer agent execution logic.

This module contains the core agent execution loop, error handling, and tool result extraction.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic_ai import UsageLimits
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolReturnPart,
)
from ratelimit import limits, sleep_and_retry
from tenacity import Retrying

from egregora.agents.types import (
    JournalEntry,
    JournalEntryParams,
    PromptTooLargeError,
    WriterDeps,
)
from egregora.agents.writer.context import inject_profiles_context, inject_rag_context
from egregora.agents.writer.journal import (
    extract_intercalated_log,
    extract_journal_content,
    save_journal_to_file,
)
from egregora.agents.writer_helpers import process_tool_result
from egregora.agents.writer_setup import (
    configure_writer_capabilities,
    create_writer_model,
    setup_writer_agent,
)
from egregora.infra.retry import RETRY_IF, RETRY_STOP, RETRY_WAIT

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)

# Type aliases
MessageHistory = Sequence[ModelRequest | ModelResponse]
AgentModel = Any


def _process_single_tool_result(
    content: Any, tool_name: str | None, saved_posts: list[str], saved_profiles: list[str]
) -> None:
    """Process a single tool result and append to the appropriate list."""
    data = process_tool_result(content)
    if not data or data.get("status") not in ("success", "scheduled") or "path" not in data:
        return

    path = data["path"]
    if tool_name == "write_post_tool":
        saved_posts.append(path)
    elif tool_name == "write_profile_tool":
        saved_profiles.append(path)


def _extract_from_message(message: Any, saved_posts: list[str], saved_profiles: list[str]) -> None:
    """Extract tool results from a single message."""
    if hasattr(message, "parts"):
        for part in message.parts:
            if isinstance(part, ToolReturnPart):
                _process_single_tool_result(part.content, part.tool_name, saved_posts, saved_profiles)
    elif hasattr(message, "kind") and message.kind == "tool-return":
        tool_name = getattr(message, "tool_name", None)
        _process_single_tool_result(message.content, tool_name, saved_posts, saved_profiles)


def extract_tool_results(messages: MessageHistory) -> tuple[list[str], list[str]]:
    """Extract saved post and profile document IDs from agent message history."""
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    for message in messages:
        _extract_from_message(message, saved_posts, saved_profiles)

    return saved_posts, saved_profiles


@sleep_and_retry
@limits(calls=100, period=60)
async def write_posts_with_pydantic_agent(
    *,
    prompt: str,
    config: EgregoraConfig,
    context: WriterDeps,
    test_model: AgentModel | None = None,
) -> tuple[list[str], list[str]]:
    """Execute the writer flow using Pydantic-AI agent tooling."""
    logger.info("Running writer via Pydantic-AI backend")

    active_capabilities = configure_writer_capabilities(config, context)
    if active_capabilities:
        caps_list = ", ".join(capability.name for capability in active_capabilities)
        logger.info("Writer capabilities enabled: %s", caps_list)

    model = await create_writer_model(config, context, prompt, test_model)
    agent = setup_writer_agent(model, prompt, active_capabilities)

    # Re-attach dynamic system prompts that were defined in the original writer.py
    # because setup_writer_agent only attaches static configuration.
    # Actually, let's modify setup_writer_agent or just attach them here.
    # The original implementation had them inline.
    agent.system_prompt(inject_rag_context)
    agent.system_prompt(inject_profiles_context)

    if context.resources.quota:
        context.resources.quota.reserve(1)

    # Define usage limits
    usage_limits = UsageLimits(
        request_limit=15,  # Reasonable limit for tool loops
        # response_tokens_limit=... # Optional
    )

    result = None
    # Use tenacity for retries
    for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
        with attempt:
            # Use async run since we're in an async context
            result = await agent.run(
                "Analyze the conversation context provided and write posts/profiles as needed.",
                deps=context,
                usage_limits=usage_limits,
            )

    if not result:
        # Should be unreachable due to reraise=True
        msg = "Agent failed after retries"
        raise RuntimeError(msg)

    usage = result.usage()
    if context.resources.usage:
        context.resources.usage.record(usage)
    saved_posts, saved_profiles = extract_tool_results(result.all_messages())
    intercalated_log = extract_intercalated_log(result.all_messages())
    if not intercalated_log:
        fallback_content = extract_journal_content(result.all_messages())
        if fallback_content:
            # Strip frontmatter if present (to avoid double frontmatter)
            if fallback_content.strip().startswith("---"):
                try:
                    _, _, body = fallback_content.strip().split("---", 2)
                    fallback_content = body.strip()
                except ValueError:
                    pass  # Failed to split, keep original

            intercalated_log = [JournalEntry("journal", fallback_content, datetime.now(tz=UTC))]
        else:
            intercalated_log = [
                JournalEntry(
                    "journal",
                    "Writer agent completed without emitting a detailed reasoning trace.",
                    datetime.now(tz=UTC),
                )
            ]
    save_journal_to_file(
        JournalEntryParams(
            intercalated_log=intercalated_log,
            window_label=context.window_label,
            output_format=context.resources.output,
            posts_published=len(saved_posts),
            profiles_updated=len(saved_profiles),
            window_start=context.window_start,
            window_end=context.window_end,
            total_tokens=result.usage().total_tokens if result.usage() else 0,
        )
    )

    logger.info(
        "Writer agent completed: period=%s posts=%d profiles=%d tokens=%d",
        context.window_label,
        len(saved_posts),
        len(saved_profiles),
        result.usage().total_tokens if result.usage() else 0,
    )

    return saved_posts, saved_profiles


async def execute_writer_with_error_handling(
    prompt: str,
    config: EgregoraConfig,
    deps: WriterDeps,
) -> tuple[list[str], list[str]]:
    """Execute writer agent with proper error handling.

    Returns:
        Tuple of (saved_posts, saved_profiles)

    Raises:
        PromptTooLargeError: If prompt exceeds model context window (propagated unchanged)
        RuntimeError: For other agent failures (wrapped with context)

    """
    try:
        return await write_posts_with_pydantic_agent(
            prompt=prompt,
            config=config,
            context=deps,
        )
    except Exception as exc:
        if isinstance(exc, PromptTooLargeError):
            raise

        cause = f"{type(exc).__name__}: {exc}".strip()
        msg = f"Writer agent failed for {deps.window_label} ({cause})"
        logger.exception(msg)
        raise RuntimeError(msg) from exc
