"""Helper functions for writer agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext

from egregora.agents.model_limits import (
    PromptTooLargeError,
    get_model_context_limit,
)
from egregora.agents.model_limits import (
    validate_prompt_fits as _validate_prompt_fits,
)
from egregora.agents.types import (
    AnnotationResult,
    PostMetadata,
    ReadProfileResult,
    WritePostResult,
    WriteProfileResult,
    WriterDeps,
)
from egregora.data_primitives.document import DocumentType
from egregora.rag import RAGQueryRequest

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from egregora.agents.capabilities import AgentCapability
    from egregora.agents.types import (
        WriterAgentReturn,
    )
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)


def _process_tool_result(content: Any) -> dict[str, Any] | None:
    """Parse tool result content into a dictionary if valid."""
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (ValueError, json.JSONDecodeError):
            return None
    if hasattr(content, "model_dump"):
        return content.model_dump()
    if isinstance(content, dict):
        return content
    return None


# ============================================================================
# Tool Definitions
# ============================================================================


def register_writer_tools(
    agent: Agent[WriterDeps, WriterAgentReturn],
    capabilities: list[AgentCapability],
) -> None:
    """Attach tool implementations to the agent via core tools and capabilities."""

    @agent.tool
    def write_post_tool(ctx: RunContext[WriterDeps], metadata: PostMetadata, content: str) -> WritePostResult:
        meta_dict = metadata.model_dump(exclude_none=True)
        meta_dict["model"] = ctx.deps.model_name
        return ctx.deps.write_post(meta_dict, content)

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str) -> ReadProfileResult:
        return ctx.deps.read_profile(author_uuid)

    @agent.tool
    def write_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str, content: str) -> WriteProfileResult:
        return ctx.deps.write_profile(author_uuid, content)

    @agent.tool
    def annotate_conversation_tool(
        ctx: RunContext[WriterDeps], parent_id: str, parent_type: str, commentary: str
    ) -> AnnotationResult:
        """Annotate a message or another annotation with commentary."""
        return ctx.deps.annotate(parent_id, parent_type, commentary)

    for capability in capabilities:
        logger.debug("Registering capability: %s", capability.name)
        capability.register(agent)


# ============================================================================
# Context Building (RAG & Profiles)
# ============================================================================


# RAG Context Building logic removed as it requires dynamic dependency injection
# which is better handled by @agent.system_prompt within writer_setup.py.
# The previous implementation relied on global state which we are removing.


def load_profiles_context(active_authors: list[str], output_sink: Any) -> str:
    """Load profiles for top active authors via output_sink.
    
    Uses output_sink.read_document() to read profiles from the unified
    output directory (e.g., posts/ in MkDocs), rather than direct file access.
    
    Args:
        active_authors: List of author UUIDs to load profiles for
        output_sink: OutputSink instance that knows where profiles are stored
        
    Returns:
        Formatted string with profile context for each author
    """
    if not active_authors:
        return ""
    logger.info("Loading profiles for %s active authors", len(active_authors))

    parts = [
        "\n\n## Active Participants (Profiles):\n",
        "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n",
    ]

    for author_uuid in active_authors:
        try:
            doc = output_sink.read_document(DocumentType.PROFILE, author_uuid)
            profile_content = doc.content if doc else ""
        except (OSError, ValueError, AttributeError) as exc:
            logger.debug("Could not read profile for %s: %s", author_uuid, exc)
            profile_content = ""
        
        parts.append(f"### Author: {author_uuid}\n")
        if profile_content:
            parts.append(f"{profile_content}\n\n")
        else:
            parts.append("(No profile yet - first appearance)\n\n")

    profiles_context = "".join(parts)
    logger.info("Profiles context: %s characters", len(profiles_context))
    return profiles_context


def validate_prompt_fits(
    prompt: str,
    model_name: str,
    config: EgregoraConfig,
    window_label: str,
) -> None:
    """Validate prompt fits within model context window limits."""
    max_prompt_tokens = getattr(config.pipeline, "max_prompt_tokens", 100_000)
    use_full_context_window = getattr(config.pipeline, "use_full_context_window", False)

    fits, estimated_tokens, _effective_limit = _validate_prompt_fits(
        prompt,
        model_name,
        max_prompt_tokens=max_prompt_tokens,
        use_full_context_window=use_full_context_window,
    )

    if not fits:
        model_limit = get_model_context_limit(model_name)
        model_effective_limit = int(model_limit * 0.9)

        if estimated_tokens > model_effective_limit:
            logger.error(
                "Prompt exceeds limit: %d > %d for %s (window: %s)",
                estimated_tokens,
                model_effective_limit,
                model_name,
                window_label,
            )
            raise PromptTooLargeError(
                estimated_tokens=estimated_tokens,
                effective_limit=model_effective_limit,
                model_name=model_name,
                window_id=window_label,
            )
