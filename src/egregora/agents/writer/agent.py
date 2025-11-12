"""Pydantic-AI powered writer agent.

This module implements the writer workflow using Pydantic-AI.
It exposes ``write_posts_with_pydantic_agent`` which mirrors the signature of
``write_posts_for_window`` but routes the LLM conversation through a
``pydantic_ai.Agent`` instance. The implementation keeps the existing tool
surface (write_post, read/write_profile, search_media, annotate, banner)
so the rest of the pipeline can remain unchanged during the migration.

At the moment this backend is opt-in via the ``EGREGORA_LLM_BACKEND`` flag.

MODERN (Phase 1): Deps are frozen/immutable, no mutation in tools.
MODERN (Phase 2): Uses WriterRuntimeContext to reduce parameters.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

try:
    from pydantic_ai import Agent, ModelMessagesTypeAdapter, RunContext
except ImportError:
    from pydantic_ai import Agent, RunContext

    class ModelMessagesTypeAdapter:
        """Lightweight shim mirroring the adapter interface used in tests."""

        @staticmethod
        def dump_json(messages: object) -> str:
            if hasattr(messages, "model_dump_json"):
                return messages.model_dump_json(indent=2)
            if hasattr(messages, "model_dump"):
                return json.dumps(messages.model_dump(mode="json"), indent=2)
            if hasattr(messages, "to_json"):
                return messages.to_json(indent=2)
            return json.dumps(messages, indent=2, default=str)


from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

from egregora.agents.banner import generate_banner_for_post, is_banner_generation_available
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.shared.rag import VectorStore, is_rag_available, query_media
from egregora.config.schema import EgregoraConfig
from egregora.core.document import Document, DocumentType
from egregora.database.streaming import stream_ibis
from egregora.storage.output_format import OutputFormat
from egregora.storage.url_convention import UrlContext, UrlConvention
from egregora.utils.logfire_config import logfire_info, logfire_span

if TYPE_CHECKING:
    from pydantic_ai.result import RunResult

    from egregora.agents.shared.annotations import AnnotationStore

logger = logging.getLogger(__name__)

# Type aliases for improved type safety
# Note: Some types remain as Any due to Pydantic limitations with Protocol validation
MessageHistory = Sequence[ModelRequest | ModelResponse]
LLMClient = Any  # Could be various client types (Google, Anthropic, etc.)
AgentModel = Any  # Model specification (string or configured model object)


@dataclass(frozen=True, slots=True)
class WriterRuntimeContext:
    """Runtime context for writer agent execution.

    MODERN (Phase 2): Bundles runtime parameters to reduce function signatures.
    MODERN (Phase 4): Uses OutputFormat for all document persistence.
    MODERN (Phase 5): Removed redundant storage protocols in favor of OutputFormat.

    Windows are identified by (start_time, end_time) tuple, not artificial IDs.
    This makes them stable across config changes and more meaningful for logging.

    Architecture (Phase 5 - Simplified, Phase 6 - Read Support):
    - Core calculates URLs using url_convention directly
    - Core requests persistence via output_format.serve(document)
    - Core reads documents via output_format.read_document()
    - Single abstraction (OutputFormat) replaces all storage protocols
    """

    # Time window
    start_time: datetime
    end_time: datetime

    # MODERN Phase 4+6: Backend-agnostic publishing (single abstraction)
    url_convention: UrlConvention
    url_context: UrlContext
    output_format: OutputFormat

    # Pre-constructed stores (injected, not built from paths)
    rag_store: VectorStore
    annotations_store: AnnotationStore | None

    # LLM client
    client: LLMClient

    # Prompt templates directory (resolved by caller, not constructed here)
    prompts_dir: Path | None = None

    # Paths still needed for specific features (non-document persistence)
    # TODO: Further refactoring could inject specialized handlers instead
    output_dir: Path | None = None  # Used for banner generation fallback
    rag_dir: Path | None = None  # Used for RAG queries
    site_root: Path | None = None  # Used for banner generation


class PostMetadata(BaseModel):
    """Metadata schema for the write_post tool."""

    title: str
    slug: str
    date: str
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    authors: list[str] = Field(default_factory=list)
    category: str | None = None


class WritePostResult(BaseModel):
    status: str
    path: str


class WriteProfileResult(BaseModel):
    status: str
    path: str


class ReadProfileResult(BaseModel):
    content: str


class MediaItem(BaseModel):
    media_type: str | None = None
    media_path: str | None = None
    original_filename: str | None = None
    description: str | None = None
    similarity: float | None = None


class SearchMediaResult(BaseModel):
    results: list[MediaItem]


class AnnotationResult(BaseModel):
    status: str
    annotation_id: str | None = None
    parent_id: str | None = None
    parent_type: str | None = None


class BannerResult(BaseModel):
    status: str
    path: str | None = None


class WriterAgentReturn(BaseModel):
    """Final assistant response when the agent finishes."""

    summary: str | None = None
    notes: str | None = None


class WriterAgentState(BaseModel):
    """Immutable dependencies passed to agent tools.

    MODERN (Phase 1): This is now frozen to prevent mutation in tools.
    MODERN (Phase 4): Uses OutputFormat for all document persistence.
    MODERN (Phase 5): Removed redundant storage protocols in favor of OutputFormat.
    MODERN (Phase 6): OutputFormat now supports reading documents.
    Results are extracted from the agent's message history instead of being
    tracked via mutation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    # Window identification
    window_id: str

    # MODERN Phase 4+6: Backend-agnostic publishing (single abstraction with read support)
    # Note: Using Any for protocol types since Pydantic can't validate Protocols
    url_convention: Any  # UrlConvention protocol
    url_context: Any  # UrlContext dataclass
    output_format: Any  # OutputFormat protocol (read + write)

    # Pre-constructed stores
    rag_store: Any  # VectorStore
    annotations_store: Any | None  # AnnotationStore protocol

    # LLM client
    batch_client: LLMClient

    # RAG configuration
    embedding_model: str
    retrieval_mode: str
    retrieval_nprobe: int | None
    retrieval_overfetch: int | None

    # Paths still needed for specific features (non-document persistence)
    output_dir: Path | None = None  # Used for banner generation fallback
    rag_dir: Path | None = None  # Used for RAG queries
    site_root: Path | None = None  # Used for banner generation


def _extract_thinking_content(messages: MessageHistory) -> list[str]:
    """Extract thinking/reasoning content from agent message history.

    Parses ModelResponse messages to find ThinkingPart objects containing
    the model's step-by-step reasoning process.

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        List of thinking content strings

    """
    thinking_contents: list[str] = []

    for message in messages:
        # Check if this is a ModelResponse message
        if isinstance(message, ModelResponse):
            # Iterate through parts to find ThinkingPart
            thinking_contents.extend(part.content for part in message.parts if isinstance(part, ThinkingPart))

    return thinking_contents


def _extract_freeform_content(messages: MessageHistory) -> str:
    """Extract freeform content from agent message history.

    Freeform content is plain text output from the model that's NOT a tool call.
    This is typically the model's continuity journal / reflection memo.

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        Combined freeform content as a single string

    """
    freeform_parts: list[str] = []

    for message in messages:
        # Check if this is a ModelResponse message
        if isinstance(message, ModelResponse):
            # Iterate through parts to find TextPart (non-tool text output)
            freeform_parts.extend(part.content for part in message.parts if isinstance(part, TextPart))

    return "\n\n".join(freeform_parts).strip()


@dataclass(frozen=True)
class JournalEntry:
    """Represents a single entry in the intercalated journal log.

    Each entry is one of: thinking, freeform text, or tool usage.
    Entries preserve the actual execution order from the agent's message history.
    """

    entry_type: str  # "thinking", "freeform", "tool_call", "tool_return"
    content: str
    timestamp: datetime | None = None
    tool_name: str | None = None


def _extract_intercalated_log(messages: MessageHistory) -> list[JournalEntry]:
    """Extract intercalated journal log preserving actual execution order.

    Processes agent message history to create a timeline showing:
    - Model thinking/reasoning
    - Freeform text output
    - Tool calls and their returns

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        List of JournalEntry objects in chronological order

    """
    entries: list[JournalEntry] = []

    for message in messages:
        # Handle ModelResponse (contains thinking and freeform output)
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ThinkingPart):
                    entries.append(
                        JournalEntry(
                            entry_type="thinking",
                            content=part.content,
                            timestamp=getattr(message, "timestamp", None),
                        )
                    )
                elif isinstance(part, TextPart):
                    entries.append(
                        JournalEntry(
                            entry_type="freeform",
                            content=part.content,
                            timestamp=getattr(message, "timestamp", None),
                        )
                    )
                elif isinstance(part, ToolCallPart):
                    # Format tool call
                    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
                    tool_call_content = f"Tool: {part.tool_name}\nArguments:\n{args_str}"
                    entries.append(
                        JournalEntry(
                            entry_type="tool_call",
                            content=tool_call_content,
                            timestamp=getattr(message, "timestamp", None),
                            tool_name=part.tool_name,
                        )
                    )
                elif isinstance(part, ToolReturnPart):
                    # Format tool return
                    result_str = str(part.content) if hasattr(part, "content") else "No result"
                    tool_return_content = f"Result: {result_str}"
                    entries.append(
                        JournalEntry(
                            entry_type="tool_return",
                            content=tool_return_content,
                            timestamp=getattr(message, "timestamp", None),
                            tool_name=getattr(part, "tool_name", None),
                        )
                    )

        # Handle ModelRequest (contains tool calls from model side)
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
                    tool_call_content = f"Tool: {part.tool_name}\nArguments:\n{args_str}"
                    entries.append(
                        JournalEntry(
                            entry_type="tool_call",
                            content=tool_call_content,
                            timestamp=getattr(message, "timestamp", None),
                            tool_name=part.tool_name,
                        )
                    )

    return entries


def _save_journal_to_file(
    intercalated_log: list[JournalEntry],
    window_label: str,
    output_format: OutputFormat,
) -> str | None:
    """Save journal entry with intercalated thinking, freeform, and tool usage to markdown file.

    Args:
        intercalated_log: List of journal entries in chronological order
        window_label: Human-readable window identifier (e.g., "2025-01-15 10:00 to 12:00")
        output_format: OutputFormat instance for document persistence

    Returns:
        Journal identifier (opaque string), or None if no content

    """
    # Skip if no content at all
    if not intercalated_log:
        return None

    # Load template from templates directory
    templates_dir = Path(__file__).parent.parent.parent / "templates"
    if not templates_dir.exists():
        logger.warning("Templates directory not found: %s", templates_dir)
        return None

    try:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape(enabled_extensions=())
        )
        template = env.get_template("journal.md.jinja")
    except (OSError, ValueError):  # TemplateNotFound, file I/O errors
        logger.exception("Failed to load journal template")
        return None

    # Render journal content
    now_utc = datetime.now(tz=UTC)
    try:
        journal_content = template.render(
            window_label=window_label,
            date=now_utc.strftime("%Y-%m-%d"),
            created=now_utc.isoformat(),
            intercalated_log=intercalated_log,
        )
    except (TypeError, ValueError):  # Template rendering errors
        logger.exception("Failed to render journal template")
        return None

    # Write using OutputFormat
    try:
        doc = Document(
            content=journal_content,
            type=DocumentType.JOURNAL,
            metadata={"window_label": window_label, "date": now_utc.strftime("%Y-%m-%d")},
            source_window=window_label,
        )
        output_format.serve(doc)
        logger.info("Saved journal entry: %s", doc.document_id)
        return doc.document_id
    except Exception:  # Broad catch: journal is non-critical, various backends may raise different exceptions
        logger.exception("Failed to write journal for window %s", window_label)
        return None


def _parse_content_to_dict(content: Any) -> dict[str, Any] | None:
    """Parse tool result content into a dictionary.

    Handles multiple content formats:
    - JSON strings
    - Pydantic models with model_dump()
    - Objects with __dict__
    - Raw dictionaries

    Args:
        content: Content to parse (Any type needed: str, Pydantic model, dict, or arbitrary object)

    Returns:
        Parsed dictionary or None if parsing fails

    """
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None
    if hasattr(content, "model_dump"):
        return content.model_dump()
    if hasattr(content, "__dict__"):
        return vars(content)
    if isinstance(content, dict):
        return content
    return None


def _categorize_tool_result(tool_name: str | None, doc_id: str) -> tuple[str | None, str]:
    """Determine if tool result is a post or profile.

    Uses tool name first, falls back to path heuristics for legacy messages.

    Args:
        tool_name: Tool name if available (e.g., "write_post_tool")
        doc_id: Document ID/path string

    Returns:
        Tuple of ("post"|"profile"|None, doc_id). None if type cannot be determined.

    """
    # Primary: Use tool name
    if tool_name == "write_post_tool":
        return ("post", doc_id)
    if tool_name == "write_profile_tool":
        return ("profile", doc_id)

    # Fallback: Use path heuristics for legacy messages
    if "/posts/" in doc_id or doc_id.endswith(".md"):
        return ("post", doc_id)
    if "/profiles/" in doc_id:
        return ("profile", doc_id)

    return (None, doc_id)


def _extract_from_success_result(data: dict[str, Any], tool_name: str | None) -> tuple[list[str], list[str]]:
    """Extract document IDs from a successful tool result dictionary.

    Args:
        data: Parsed tool result dictionary
        tool_name: Tool name (used to categorize result)

    Returns:
        Tuple of (saved_posts, saved_profiles)

    """
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    if data.get("status") == "success" and "path" in data:
        doc_id = data["path"]
        result_type, doc_id = _categorize_tool_result(tool_name, doc_id)

        if result_type == "post":
            saved_posts.append(doc_id)
        elif result_type == "profile":
            saved_profiles.append(doc_id)

    return (saved_posts, saved_profiles)


def _extract_from_tool_return_part(part: ToolReturnPart) -> tuple[list[str], list[str]]:
    """Extract document IDs from a ToolReturnPart message.

    Args:
        part: ToolReturnPart with parsed result

    Returns:
        Tuple of (saved_posts, saved_profiles)

    """
    parsed = _parse_content_to_dict(part.content)
    if parsed is None:
        return ([], [])

    return _extract_from_success_result(parsed, part.tool_name)


def _extract_from_legacy_tool_return(message: Any) -> tuple[list[str], list[str]]:
    """Extract document IDs from legacy tool-return message.

    Args:
        message: Legacy tool-return message with kind="tool-return"
                 (Any type needed: legacy messages have arbitrary structure)

    Returns:
        Tuple of (saved_posts, saved_profiles)

    """
    parsed = _parse_content_to_dict(message.content)
    if parsed is None:
        return ([], [])

    tool_name = getattr(message, "tool_name", None)
    return _extract_from_success_result(parsed, tool_name)


def _extract_tool_results(messages: MessageHistory) -> tuple[list[str], list[str]]:
    """Extract saved post and profile document IDs from agent message history.

    Parses the agent's tool call results to find WritePostResult and
    WriteProfileResult returns. Uses tool names to distinguish document types
    instead of parsing filesystem paths (supports opaque document IDs).

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        Tuple of (saved_posts, saved_profiles) as lists of document IDs

    """
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    try:
        for message in messages:
            # Handle ModelResponse messages with parts
            if hasattr(message, "parts"):
                for part in message.parts:
                    if isinstance(part, ToolReturnPart):
                        posts, profiles = _extract_from_tool_return_part(part)
                        saved_posts.extend(posts)
                        saved_profiles.extend(profiles)

            # Handle legacy tool-return messages
            elif hasattr(message, "kind") and message.kind == "tool-return":
                posts, profiles = _extract_from_legacy_tool_return(message)
                saved_posts.extend(posts)
                saved_profiles.extend(profiles)

    except (AttributeError, TypeError) as e:
        logger.debug("Could not parse tool results: %s", e)

    return (saved_posts, saved_profiles)


def _register_writer_tools(
    agent: Agent[WriterAgentState, WriterAgentReturn],
    *,
    enable_banner: bool = False,
    enable_rag: bool = False,
) -> None:
    """Attach tool implementations to the agent.

    NOTE: This function is 140 lines long and should be refactored. Consider:
    - Extracting each tool decorator into separate functions
    - Using a tool registry pattern
    - Separating conditional tool registration logic

    Args:
        agent: The writer agent to register tools with
        enable_banner: Whether to register banner generation tool (requires GOOGLE_API_KEY)
        enable_rag: Whether to register RAG search tools (requires GOOGLE_API_KEY)

    """

    @agent.tool
    def write_post_tool(
        ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str
    ) -> WritePostResult:
        # MODERN (Phase 4): Backend-agnostic publishing
        # 1. Create Document object
        doc = Document(
            content=content,
            type=DocumentType.POST,
            metadata=metadata.model_dump(exclude_none=True),
            source_window=ctx.deps.window_id,
        )

        # 2. Calculate URL using convention (Core's responsibility)
        url = ctx.deps.url_convention.canonical_url(doc, ctx.deps.url_context)

        # 3. Request persistence (Format's responsibility)
        ctx.deps.output_format.serve(doc)

        logger.info("Writer agent saved post at URL: %s (doc_id: %s)", url, doc.document_id)
        return WritePostResult(status="success", path=url)  # Return URL as "path"

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterAgentState], author_uuid: str) -> ReadProfileResult:
        # MODERN Phase 6: Read via OutputFormat (backend-agnostic)
        doc = ctx.deps.output_format.read_document(DocumentType.PROFILE, author_uuid)
        if doc:
            content = doc.content
        else:
            content = "No profile exists yet."
        return ReadProfileResult(content=content)

    @agent.tool
    def write_profile_tool(
        ctx: RunContext[WriterAgentState], author_uuid: str, content: str
    ) -> WriteProfileResult:
        # MODERN (Phase 4): Backend-agnostic publishing
        # 1. Create Document object
        doc = Document(
            content=content,
            type=DocumentType.PROFILE,
            metadata={"uuid": author_uuid},
            source_window=ctx.deps.window_id,
        )

        # 2. Calculate URL using convention (Core's responsibility)
        url = ctx.deps.url_convention.canonical_url(doc, ctx.deps.url_context)

        # 3. Request persistence (Format's responsibility)
        ctx.deps.output_format.serve(doc)

        logger.info("Writer agent saved profile at URL: %s (doc_id: %s)", url, doc.document_id)
        return WriteProfileResult(status="success", path=url)  # Return URL as "path"

    if enable_rag:

        @agent.tool
        def search_media_tool(
            ctx: RunContext[WriterAgentState],
            query: str,
            media_types: list[str] | None = None,
            limit: int = 5,
        ) -> SearchMediaResult:
            # Use pre-constructed rag_store instead of building from path
            results = query_media(
                query=query,
                store=ctx.deps.rag_store,
                media_types=media_types,
                top_k=limit,
                min_similarity=0.7,
                embedding_model=ctx.deps.embedding_model,
                retrieval_mode=ctx.deps.retrieval_mode,
                retrieval_nprobe=ctx.deps.retrieval_nprobe,
                retrieval_overfetch=ctx.deps.retrieval_overfetch,
            )
            items: list[MediaItem] = []
            for batch in stream_ibis(results, ctx.deps.rag_store._client, batch_size=100):
                items.extend(
                    MediaItem(
                        media_type=row.get("media_type"),
                        media_path=row.get("media_path"),
                        original_filename=row.get("original_filename"),
                        description=row.get("description"),
                        similarity=row.get("similarity"),
                    )
                    for row in batch.iter_rows(named=True)
                )
            return SearchMediaResult(results=items)

    @agent.tool
    def annotate_conversation_tool(
        ctx: RunContext[WriterAgentState], parent_id: str, parent_type: str, commentary: str
    ) -> AnnotationResult:
        if ctx.deps.annotations_store is None:
            msg = "Annotation store is not configured"
            raise RuntimeError(msg)
        annotation = ctx.deps.annotations_store.save_annotation(
            parent_id=parent_id, parent_type=parent_type, commentary=commentary
        )
        return AnnotationResult(
            status="success",
            annotation_id=annotation.id,
            parent_id=annotation.parent_id,
            parent_type=annotation.parent_type,
        )

    if enable_banner:

        @agent.tool
        def generate_banner_tool(
            ctx: RunContext[WriterAgentState], post_slug: str, title: str, summary: str
        ) -> BannerResult:
            # Save banners to media/images/ at site root (same as other media)
            # Banners will be enriched through the same pipeline as other media
            if ctx.deps.site_root:
                banner_output_dir = ctx.deps.site_root / "media" / "images"
            else:
                # Fallback: use output_dir (posts_dir) if site_root not available
                banner_output_dir = ctx.deps.output_dir / "media" / "images"

            banner_path = generate_banner_for_post(
                post_title=title, post_summary=summary, output_dir=banner_output_dir, slug=post_slug
            )
            if banner_path:
                return BannerResult(status="success", path=str(banner_path))
            return BannerResult(status="failed", path=None)


def _setup_agent_and_state(
    config: EgregoraConfig,
    context: WriterRuntimeContext,
    test_model: AgentModel | None = None,
) -> tuple[Agent[WriterAgentState, WriterAgentReturn], WriterAgentState, str]:
    """Set up writer agent and execution state.

    Args:
        config: Egregora configuration
        context: Runtime context
        test_model: Optional test model override (string or configured model object)

    Returns:
        Tuple of (agent, state, window_label)

    """
    # Extract model names from config
    model_name = test_model if test_model is not None else config.models.writer
    embedding_model = config.models.embedding
    retrieval_mode = config.rag.mode
    retrieval_nprobe = config.rag.nprobe
    retrieval_overfetch = config.rag.overfetch

    # Create and configure agent
    agent = Agent[WriterAgentState, WriterAgentReturn](model=model_name, deps_type=WriterAgentState)
    _register_writer_tools(
        agent, enable_banner=is_banner_generation_available(), enable_rag=is_rag_available()
    )

    # Generate window label for logging
    window_label = f"{context.start_time:%Y-%m-%d %H:%M} to {context.end_time:%H:%M}"

    # Build execution state
    state = WriterAgentState(
        window_id=window_label,
        # MODERN Phase 6: OutputFormat with read support
        url_convention=context.url_convention,
        url_context=context.url_context,
        output_format=context.output_format,
        # Stores
        rag_store=context.rag_store,
        annotations_store=context.annotations_store,
        # LLM client
        batch_client=context.client,
        # RAG configuration
        embedding_model=embedding_model,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        # Paths for non-document features
        output_dir=context.output_dir,
        rag_dir=context.rag_dir,
        site_root=context.site_root,
    )

    return agent, state, window_label


def _validate_prompt_fits(
    prompt: str,
    model_name: str,
    config: EgregoraConfig,
    window_label: str,
) -> None:
    """Validate prompt fits within model context window limits.

    Args:
        prompt: System prompt to validate
        model_name: Name of the LLM model
        config: Egregora configuration with token limits
        window_label: Window identifier for logging

    Raises:
        PromptTooLargeError: If prompt exceeds hard model limit

    """
    from egregora.agents.model_limits import (
        PromptTooLargeError,
        get_model_context_limit,
        validate_prompt_fits,
    )

    max_prompt_tokens = getattr(config.pipeline, "max_prompt_tokens", 100_000)
    use_full_context_window = getattr(config.pipeline, "use_full_context_window", False)

    fits, estimated_tokens, effective_limit = validate_prompt_fits(
        prompt,
        model_name,
        max_prompt_tokens=max_prompt_tokens,
        use_full_context_window=use_full_context_window,
    )

    if not fits:
        model_limit = get_model_context_limit(model_name)
        model_effective_limit = int(model_limit * 0.9)

        if estimated_tokens <= model_effective_limit:
            logger.warning(
                "Prompt exceeds %dk cap (%d tokens) but fits in model limit (%d tokens) for %s (window: %s) - allowing as exception (likely single large message)",
                max_prompt_tokens // 1000,
                estimated_tokens,
                model_effective_limit,
                model_name,
                window_label,
            )
        else:
            logger.error(
                "Prompt exceeds model hard limit: %d tokens > %d limit for %s (window: %s) - will split window",
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
    else:
        logger.info(
            "Prompt fits: %d tokens / %d limit (%.1f%% usage) for %s",
            estimated_tokens,
            effective_limit,
            (estimated_tokens / effective_limit) * 100,
            model_name,
        )


def _run_agent_with_retries(
    agent: Agent[WriterAgentState, WriterAgentReturn],
    state: WriterAgentState,
    prompt: str,
) -> RunResult[WriterAgentReturn]:
    """Run agent with exponential backoff retry logic.

    Args:
        agent: Configured writer agent
        state: Agent execution state
        prompt: System prompt

    Returns:
        Agent execution result with message history and usage metrics

    """
    max_attempts = 3
    result: RunResult[WriterAgentReturn] | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = agent.run_sync(prompt, deps=state)
            break
        except Exception as exc:  # Broad catch: retry on any error (network, API, timeout, etc.)
            if attempt == max_attempts:
                logger.exception("Writer agent failed after %s attempts", attempt)
                raise
            delay = attempt * 2
            logger.warning(
                "Writer agent attempt %s/%s failed: %s. Retrying in %ss...",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay)

    # Type narrowing: result will always be set if we reach here (exception raised on final failure)
    assert result is not None, "Result should be set after successful retry or exception raised"
    return result


def _log_agent_completion(
    result: RunResult[WriterAgentReturn],
    saved_posts: list[str],
    saved_profiles: list[str],
    intercalated_log: list[JournalEntry],
    window_label: str,
) -> None:
    """Log agent completion metrics and results.

    Args:
        result: Agent execution result with message history and usage metrics
        saved_posts: List of created post IDs
        saved_profiles: List of updated profile IDs
        intercalated_log: Journal entries from execution
        window_label: Window identifier for logging

    """
    result_payload = getattr(result, "output", getattr(result, "data", result))
    usage = result.usage()

    logfire_info(
        "Writer agent completed",
        period=window_label,
        posts_created=len(saved_posts),
        profiles_updated=len(saved_profiles),
        journal_saved=True,
        journal_entries=len(intercalated_log),
        journal_thinking_entries=sum(1 for e in intercalated_log if e.entry_type == "thinking"),
        journal_freeform_entries=sum(1 for e in intercalated_log if e.entry_type == "freeform"),
        journal_tool_calls=sum(1 for e in intercalated_log if e.entry_type == "tool_call"),
        tokens_total=usage.total_tokens if usage else 0,
        tokens_input=usage.input_tokens if usage else 0,
        tokens_output=usage.output_tokens if usage else 0,
        tokens_cache_write=usage.cache_write_tokens if usage else 0,
        tokens_cache_read=usage.cache_read_tokens if usage else 0,
        tokens_input_audio=usage.input_audio_tokens if usage else 0,
        tokens_cache_audio_read=usage.cache_audio_read_tokens if usage else 0,
        tokens_thinking=(usage.details or {}).get("thinking_tokens", 0) if usage else 0,
        tokens_reasoning=(usage.details or {}).get("reasoning_tokens", 0) if usage else 0,
        usage_details=usage.details if usage and usage.details else {},
    )
    logger.info("Writer agent finished with summary: %s", getattr(result_payload, "summary", None))


def _record_agent_conversation(
    result: RunResult[WriterAgentReturn],
    context: WriterRuntimeContext,
) -> None:
    """Record agent conversation to file if configured.

    Args:
        result: Agent execution result with message history
        context: Runtime context with start_time and output paths

    """
    record_dir = os.environ.get("EGREGORA_LLM_RECORD_DIR")
    if not record_dir:
        return

    try:
        output_path = Path(record_dir).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        filename = output_path / f"writer-{context.start_time:%Y%m%d_%H%M%S}-{timestamp}.json"
        payload = ModelMessagesTypeAdapter.dump_json(result.all_messages())
        filename.write_bytes(payload)
        logger.info("Recorded writer agent conversation to %s", filename)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        logger.warning("Failed to persist writer agent messages: %s", exc)


def write_posts_with_pydantic_agent(
    *,
    prompt: str,
    config: EgregoraConfig,
    context: WriterRuntimeContext,
    test_model: AgentModel | None = None,
) -> tuple[list[str], list[str]]:
    """Execute the writer flow using Pydantic-AI agent tooling.

    MODERN (Phase 2): Reduced from 12 parameters to 3 (prompt, config, context).

    Args:
        prompt: System prompt for the writer agent
        config: Egregora configuration (models, RAG, writer settings)
        context: Runtime context (paths, client, period info)
        test_model: Optional test model for unit tests (string or configured model object)

    Returns:
        Tuple (saved_posts, saved_profiles) as lists of document IDs

    """
    logger.info("Running writer via Pydantic-AI backend")

    # Setup: Create agent, state, and window label
    agent, state, window_label = _setup_agent_and_state(config, context, test_model)

    # Validate: Check prompt fits in context window
    model_name = test_model if test_model is not None else config.models.writer
    _validate_prompt_fits(prompt, model_name, config, window_label)

    # Execute: Run agent and process results
    with logfire_span("writer_agent", period=window_label, model=model_name):
        result = _run_agent_with_retries(agent, state, prompt)

        # Extract results from agent output
        saved_posts, saved_profiles = _extract_tool_results(result.all_messages())

        # Extract and save journal
        intercalated_log = _extract_intercalated_log(result.all_messages())
        _save_journal_to_file(intercalated_log, window_label, context.output_format)

        # Log comprehensive metrics
        _log_agent_completion(result, saved_posts, saved_profiles, intercalated_log, window_label)

        # Record conversation if configured
        _record_agent_conversation(result, context)

    return saved_posts, saved_profiles


class WriterStreamResult:
    """Result from streaming writer agent.

    This class is an async context manager that properly wraps pydantic-ai's
    run_stream() async context manager and adds logfire observability spans.

    Usage:
        >>> async with write_posts_with_pydantic_agent_stream(...) as result:
        ...     async for chunk in result.stream():
        ...         print(chunk)
        ...     posts, profiles = result.get_output_paths()

    """

    def __init__(
        self,
        agent: Agent[WriterAgentState, WriterAgentReturn],
        state: WriterAgentState,
        prompt: str,
        context: WriterRuntimeContext,
        model_name: str,
    ) -> None:
        self.agent = agent
        self.state = state
        self.prompt = prompt
        self.context = context
        self.model_name = model_name
        self._response = None

    async def __aenter__(self) -> Self:
        self._stream_manager = self.agent.run_stream(self.prompt, deps=self.state)
        self._response = await self._stream_manager.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if hasattr(self, "_stream_manager") and self._stream_manager:
            await self._stream_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def stream(self) -> AsyncGenerator[str, None]:
        if not self._response:
            msg = "WriterStreamResult must be used as async context manager"
            raise RuntimeError(msg)
        async for chunk in self._response.stream_text():
            yield chunk

    def get_output_paths(self) -> tuple[list[str], list[str]]:
        """Return (saved_posts, saved_profiles) after agent completes."""
        if not self._response:
            msg = "WriterStreamResult must be used as async context manager (use: async with write_posts_with_pydantic_agent_stream(...) as result)"
            raise RuntimeError(msg)

        # Extract from message history
        all_messages = getattr(self._response, "all_messages", list)()
        saved_posts, saved_profiles = _extract_tool_results(all_messages)
        return (saved_posts, saved_profiles)


async def write_posts_with_pydantic_agent_stream(
    *,
    prompt: str,
    config: EgregoraConfig,
    context: WriterRuntimeContext,
    test_model: AgentModel | None = None,
) -> WriterStreamResult:
    """Execute writer with streaming output.

    MODERN (Phase 2): Reduced from 12 parameters to 3 (prompt, config, context).

    Args:
        prompt: System prompt for the writer agent
        config: Egregora configuration (models, RAG, writer settings)
        context: Runtime context (paths, client, period info)
        test_model: Optional test model for unit tests (string or configured model object)

    Returns:
        WriterStreamResult async context manager for streaming

    """
    logger.info("Running writer via Pydantic-AI backend (streaming)")

    # Extract values from config and context (Phase 2)
    model_name = test_model if test_model is not None else config.models.writer
    embedding_model = config.models.embedding
    retrieval_mode = config.rag.mode
    retrieval_nprobe = config.rag.nprobe
    retrieval_overfetch = config.rag.overfetch

    # Generate window label from timestamps (Phase 7)
    window_label = f"{context.start_time:%Y-%m-%d %H:%M} to {context.end_time:%H:%M}"

    agent = Agent[WriterAgentState, WriterAgentReturn](model=model_name, deps_type=WriterAgentState)
    if os.environ.get("EGREGORA_STRUCTURED_OUTPUT") and test_model is None:
        _register_writer_tools(
            agent, enable_banner=is_banner_generation_available(), enable_rag=is_rag_available()
        )
    else:
        agent = Agent[WriterAgentState, str](model=model_name, deps_type=WriterAgentState)

    state = WriterAgentState(
        window_id=window_label,
        # MODERN Phase 6: OutputFormat with read support
        url_convention=context.url_convention,
        url_context=context.url_context,
        output_format=context.output_format,
        # Pre-constructed stores
        rag_store=context.rag_store,
        annotations_store=context.annotations_store,
        # LLM client
        batch_client=context.client,
        # RAG configuration
        embedding_model=embedding_model,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        # Paths for non-document features
        output_dir=context.output_dir,
        rag_dir=context.rag_dir,
        site_root=context.site_root,
    )
    return WriterStreamResult(agent, state, prompt, context, model_name)
