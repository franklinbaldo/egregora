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
from egregora.knowledge.profiles import read_profile
from egregora.rag import RAGQueryRequest, reset_backend, search

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


def build_rag_context_for_prompt(
    table_markdown: str,
    *,
    top_k: int = 5,
    cache: Any | None = None,
) -> str:
    """Build RAG context by searching for similar posts.

    Uses the new egregora.rag API to find relevant posts based on the conversation content.

    Args:
        table_markdown: Conversation content in markdown format to search against
        top_k: Number of similar posts to retrieve (default: 5)
        cache: Optional cache for RAG queries

    Returns:
        Formatted string with similar posts context, or empty string if no results

    """
    if not table_markdown or not table_markdown.strip():
        return ""

    query_text = table_markdown[:500]
    cached = _get_cached_rag_context(cache, query_text)
    if cached is not None:
        return cached

    response = _run_rag_query(query_text, top_k)
    if response is None or not response.hits:
        return ""

    context = _format_rag_hits(response.hits)
    _store_rag_context(cache, query_text, context)
    logger.info("Built RAG context with %d similar posts", len(response.hits))
    return context


def _get_cached_rag_context(cache: Any | None, query_text: str) -> str | None:
    if cache is None:
        return None
    try:
        cache_key = f"rag_context_{hash(query_text)}"
        return cache.rag.get(cache_key)
    except (AttributeError, KeyError, TypeError):
        logger.warning("Cache retrieval failed")
        return None


def _run_rag_query(query_text: str, top_k: int) -> Any | None:
    try:
        reset_backend()
        return search(RAGQueryRequest(text=query_text, top_k=top_k))
    except (ConnectionError, TimeoutError) as exc:
        logger.warning("RAG backend unavailable, continuing without context: %s", exc)
    except ValueError as exc:
        logger.warning("Invalid RAG query, continuing without context: %s", exc)
    except (AttributeError, KeyError, TypeError):
        logger.exception("Malformed RAG response, continuing without context")
    return None


def _format_rag_hits(hits: list[Any]) -> str:
    parts = [
        "\n\n## Similar Posts (for context and inspiration):\n",
        "These are similar posts from previous conversations that might provide useful context:\n\n",
    ]
    for idx, hit in enumerate(hits, 1):
        similarity_pct = int(hit.score * 100)
        parts.append(f"### Similar Post {idx} (similarity: {similarity_pct}%)\n")
        parts.append(f"{hit.text[:500]}...\n\n")
    return "".join(parts)


def _store_rag_context(cache: Any | None, query_text: str, context: str) -> None:
    if cache is None:
        return
    try:
        cache_key = f"rag_context_{hash(query_text)}"
        cache.rag.set(cache_key, context)
    except (AttributeError, KeyError, TypeError):
        logger.warning("Cache storage failed")


def load_profiles_context(active_authors: list[str], profiles_dir: Path) -> str:
    """Load profiles for top active authors."""
    if not active_authors:
        return ""
    logger.info("Loading profiles for %s active authors", len(active_authors))

    parts = [
        "\n\n## Active Participants (Profiles):\n",
        "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n",
    ]

    for author_uuid in active_authors:
        profile_content = read_profile(author_uuid, profiles_dir)
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
