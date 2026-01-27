"""Helper functions for writer agent."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from dateutil.parser import parse as parse_date
from pydantic_ai import Agent, ModelRetry, RunContext

from egregora.agents.banner.agent import is_banner_generation_available
from egregora.agents.tools.writer_tools import (
    AnnotationContext,
    AnnotationResult,
    BannerContext,
    BannerResult,
    ReadProfileResult,
    SearchMediaResult,
    ToolContext,
    WritePostResult,
    WriteProfileResult,
    annotate_conversation_impl,
    generate_banner_impl,
    read_profile_impl,
    search_media_impl,
    write_post_impl,
    write_profile_impl,
)
from egregora.agents.types import (
    PostMetadata,
    PromptTooLargeError,
    WriterAgentReturn,
    WriterDeps,
)
from egregora.data_primitives.document import DocumentType
from egregora.output_sinks.exceptions import DocumentNotFoundError
from egregora.rag import RAGQueryRequest, reset_backend, search

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)


def process_tool_result(content: Any) -> dict[str, Any] | None:
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
    config: EgregoraConfig,
) -> None:
    """Attach tool implementations to the agent.

    This function registers all available tools based on the provided configuration.

    Args:
        agent: The writer agent to register tools with.
        config: Application configuration.

    """

    # Core Tools (Always available)
    @agent.tool
    def write_post_tool(
        ctx: RunContext[WriterDeps], metadata: PostMetadata | dict | str, content: str
    ) -> WritePostResult:
        """Write a blog post with flexible metadata handling.

        Args:
            ctx: Runtime context with dependencies
            metadata: Post metadata as PostMetadata object, dict, or JSON string
            content: Markdown content for the post

        Returns:
            WritePostResult with status and document path

        """
        # Handle different metadata formats
        if isinstance(metadata, PostMetadata):
            meta_dict = metadata.model_dump(exclude_none=True)
        elif isinstance(metadata, dict):
            meta_dict = metadata
        else:  # str
            try:
                meta_dict = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning("Could not parse metadata string: %s", metadata)
                meta_dict = {}

        # Enforce strict metadata requirements
        missing_fields = []
        if "title" not in meta_dict or not meta_dict["title"]:
            missing_fields.append("title")
        if "tags" not in meta_dict or not isinstance(meta_dict["tags"], (list, str)):
            # We still allow string tags here because the next block normalizes it,
            # but if it's completely missing, we want to fail.
            missing_fields.append("tags")

        if missing_fields:
            msg = f"Missing required metadata fields: {', '.join(missing_fields)}. Please provide both 'title' and 'tags' (as a list) for the blog post."
            logger.warning(msg)
            raise ModelRetry(msg)

        # Standardize tags to list if they are provided as a string
        if isinstance(meta_dict.get("tags"), str):
            meta_dict["tags"] = [t.strip() for t in meta_dict["tags"].split(",") if t.strip()]
        elif "tags" not in meta_dict:
            meta_dict["tags"] = []  # Should be caught by missing_fields above but for safety

        # Ensure required fields for Document model
        if "id" not in meta_dict:
            # Generate a deterministic ID
            slug = meta_dict.get("slug")
            if slug:
                meta_dict["id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, slug))
            else:
                title = meta_dict.get("title", "")
                date = meta_dict.get("date", "")
                meta_dict["id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{title}-{date}"))

        if "updated" not in meta_dict and "date" in meta_dict:
            try:
                parsed_date = parse_date(meta_dict["date"])
                if parsed_date.tzinfo is None:
                    parsed_date = parsed_date.replace(tzinfo=UTC)
                meta_dict["updated"] = parsed_date.isoformat()
            except (ValueError, TypeError):
                logger.warning("Could not parse date '%s', using current time.", meta_dict["date"])
                meta_dict["updated"] = datetime.now(UTC).isoformat()
        elif "updated" not in meta_dict:
            meta_dict["updated"] = datetime.now(UTC).isoformat()
        elif isinstance(meta_dict["updated"], datetime):
            meta_dict["updated"] = meta_dict["updated"].isoformat()

        # Inject model name
        meta_dict["model"] = ctx.deps.model_name

        tool_ctx = ToolContext(
            output_sink=ctx.deps.output_sink,
            window_label=ctx.deps.window_label,
            task_store=ctx.deps.resources.task_store,
        )
        return write_post_impl(tool_ctx, meta_dict, content)

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str) -> ReadProfileResult:
        tool_ctx = ToolContext(
            output_sink=ctx.deps.output_sink,
            window_label=ctx.deps.window_label,
            task_store=ctx.deps.resources.task_store,
        )
        return read_profile_impl(tool_ctx, author_uuid)

    @agent.tool
    def write_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str, content: str) -> WriteProfileResult:
        tool_ctx = ToolContext(
            output_sink=ctx.deps.output_sink,
            window_label=ctx.deps.window_label,
            task_store=ctx.deps.resources.task_store,
        )
        return write_profile_impl(tool_ctx, author_uuid, content)

    @agent.tool
    def annotate_conversation_tool(
        ctx: RunContext[WriterDeps], parent_id: str, parent_type: str, commentary: str
    ) -> AnnotationResult:
        """Annotate a message or another annotation with commentary."""
        anno_ctx = AnnotationContext(annotations_store=ctx.deps.resources.annotations_store)
        return annotate_conversation_impl(anno_ctx, parent_id, parent_type, commentary)

    # RAG Capability
    if config.rag.enabled:
        logger.debug("Registering RAG tools (search_media)")

        @agent.tool
        def search_media(ctx: RunContext[WriterDeps], query: str, top_k: int = 5) -> SearchMediaResult:
            """Search for relevant media (images, videos, audio) in the knowledge base."""
            # Direct implementation call
            return search_media_impl(query, top_k)

    # Banner Capability
    if is_banner_generation_available():
        logger.debug("Registering Banner tools (generate_banner)")

        @agent.tool
        def generate_banner(
            ctx: RunContext[WriterDeps], post_slug: str, title: str, summary: str
        ) -> BannerResult:
            """Generate a banner image for a post."""
            # Construct context from WriterDeps
            banner_ctx = BannerContext(
                output_sink=ctx.deps.resources.output,
                task_store=ctx.deps.resources.task_store,
            )
            return generate_banner_impl(banner_ctx, post_slug, title, summary)


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
        "\n\n## Similar Posts (Reference When Relevant):\n",
        "These previous posts share themes with your current conversation. ",
        "Reference them naturally when they add context or build on ideas.\n\n",
    ]
    for idx, hit in enumerate(hits, 1):
        similarity_pct = int(hit.score * 100)

        # Extract metadata for creating proper references
        title = hit.metadata.get("title", "Untitled Post")
        slug = hit.metadata.get("slug", "unknown")
        date = hit.metadata.get("date")

        # Build relative URL (MkDocs format: posts/YYYY/MM/DD/slug/)
        # Try to extract date for proper URL structure
        url = f"posts/{slug}/"
        if date:
            try:
                # Handle various date formats (string or datetime object)
                if isinstance(date, str):
                    from datetime import datetime

                    date_obj = datetime.fromisoformat(date)
                else:
                    date_obj = date
                url = f"posts/{date_obj.year:04d}/{date_obj.month:02d}/{date_obj.day:02d}/{slug}/"
            except (ValueError, AttributeError):
                # Fallback to simple format if date parsing fails
                pass

        parts.append(f"### {idx}. [{title}]({url}) (similarity: {similarity_pct}%)\n")
        parts.append(f"{hit.text[:400]}...\n\n")
    return "".join(parts)


def _store_rag_context(cache: Any | None, query_text: str, context: str) -> None:
    if cache is None:
        return
    try:
        cache_key = f"rag_context_{hash(query_text)}"
        cache.rag.set(cache_key, context)
    except (AttributeError, KeyError, TypeError):
        logger.warning("Cache storage failed")


def load_profiles_context(active_authors: list[str], output_sink: Any) -> str:
    """Load profiles for top active authors via output sink (database-backed).

    Uses output_sink.get() which reads from the database (canonical source),
    eliminating file I/O bottleneck.

    Args:
        active_authors: List of author UUIDs to load profiles for
        output_sink: OutputSink instance (database-backed)

    Returns:
        Formatted string with profile context for each author

    """
    if not active_authors:
        return ""
    logger.info("Loading profiles for %s active authors", len(active_authors))

    parts = [
        "\n\n## Active Participants (Profiles):\n",
        "Understanding the participants helps you write posts that match their style, voice, "
        "and interests.\n\n",
    ]

    for author_uuid in active_authors:
        try:
            doc = output_sink.get(DocumentType.PROFILE, author_uuid)
            profile_content = doc.content
        except DocumentNotFoundError as exc:
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
    *,
    model_instance: Any | None = None,
) -> int:
    """Validate that prompt fits within model limits.

    Uses native SDK counting if possible, else character-based estimation.
    """
    token_count = count_tokens(prompt, model_instance)

    max_allowed = config.pipeline.max_prompt_tokens
    use_full = config.pipeline.use_full_context_window

    if token_count > max_allowed and not use_full:
        logger.warning(
            "Prompt for %s is too large (%d tokens, limit %d).",
            window_label,
            token_count,
            max_allowed,
        )
        raise PromptTooLargeError(
            limit=max_allowed,
            token_count=token_count,
            window_label=window_label,
        )

    return token_count


def count_tokens(prompt: str, model: Any | None = None) -> int:
    """Count tokens in a prompt, using native SDK if available."""
    if model and hasattr(model, "count_tokens") and callable(model.count_tokens):
        try:
            return asyncio.run(model.count_tokens(prompt))
        except Exception:
            logger.debug("Native token counting failed, falling back to estimation")

    # Fallback to conservative estimation (4 chars per token)
    return len(prompt) // 4
