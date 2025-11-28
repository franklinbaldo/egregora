"""Pydantic-AI powered writer agent.

This module implements the writer workflow using Pydantic-AI.
It exposes ``write_posts_for_window`` which routes the LLM conversation through a
``pydantic_ai.Agent`` instance.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import ibis.common.exceptions
from ibis.expr.types import Table
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.exceptions import TemplateError, TemplateNotFound
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from ratelimit import limits, sleep_and_retry

from egregora.agents.banner.agent import generate_banner, is_banner_generation_available
from egregora.agents.formatting import (
    _build_conversation_xml,
    _load_journal_memory,
)
from egregora.agents.model_limits import (
    PromptTooLargeError,
    get_model_context_limit,
    validate_prompt_fits,
)
from egregora.config.settings import EgregoraConfig, RAGSettings
from egregora.data_primitives.document import Document, DocumentType
from egregora.knowledge.profiles import get_active_authors, read_profile
from egregora.ops.media import save_media_asset
from egregora.output_adapters import OutputAdapterRegistry, create_default_output_registry
from egregora.resources.prompts import PromptManager, render_prompt
from egregora.transformations.windowing import generate_window_signature
from egregora.utils.batch import call_with_retries_sync
from egregora.utils.cache import CacheTier, PipelineCache
from egregora.utils.metrics import UsageTracker
from egregora.utils.quota import QuotaExceededError, QuotaTracker
from egregora.utils.retry import retry_sync

if TYPE_CHECKING:
    from google import genai

    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.data_primitives.protocols import OutputSink
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)

# Constants for RAG and journaling
MAX_RAG_QUERY_BYTES = 30000

# Template names
WRITER_TEMPLATE_NAME = "writer.jinja"
JOURNAL_TEMPLATE_NAME = "journal.md.jinja"
TEMPLATES_DIR_NAME = "templates"

# Fallback template identifier for cache signature
DEFAULT_TEMPLATE_SIGNATURE = "standard_writer_v1"

# Journal entry types
JOURNAL_TYPE_THINKING = "thinking"
JOURNAL_TYPE_TEXT = "journal"
JOURNAL_TYPE_TOOL_CALL = "tool_call"
JOURNAL_TYPE_TOOL_RETURN = "tool_return"

# Result keys
RESULT_KEY_POSTS = "posts"
RESULT_KEY_PROFILES = "profiles"

# Type aliases for improved type safety
MessageHistory = Sequence[ModelRequest | ModelResponse]
LLMClient = Any
AgentModel = Any


# ============================================================================
# Data Structures (Schemas)
# ============================================================================


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


@dataclass(frozen=True)
class WriterResources:
    """Explicit resources required by the writer agent."""

    # The Sink/Source for posts and profiles
    output: OutputSink

    # Knowledge Stores
    annotations_store: AnnotationStore | None
    storage: Any | None  # StorageProtocol - Required for RAG indexing

    # Configuration required for tools
    embedding_model: str
    retrieval_config: RAGSettings

    # Paths for prompt context loading
    profiles_dir: Path
    journal_dir: Path
    prompts_dir: Path | None

    # Runtime trackers
    client: genai.Client | None
    quota: QuotaTracker | None
    usage: UsageTracker | None
    output_registry: OutputAdapterRegistry | None = None


@dataclass(frozen=True)
class WriterDeps:
    """Immutable dependencies passed to agent tools.

    Replaces WriterAgentContext and WriterAgentState with a single,
    simplified structure wrapping WriterResources.
    """

    resources: WriterResources
    window_start: datetime
    window_end: datetime
    window_label: str

    @property
    def output_sink(self) -> OutputSink:
        return self.resources.output


# ============================================================================
# Tool Definitions
# ============================================================================


def register_writer_tools(
    agent: Agent[WriterDeps, WriterAgentReturn],
    *,
    enable_banner: bool = False,
    enable_rag: bool = False,
) -> None:
    """Attach tool implementations to the agent."""

    @agent.tool
    def write_post_tool(ctx: RunContext[WriterDeps], metadata: PostMetadata, content: str) -> WritePostResult:
        doc = Document(
            content=content,
            type=DocumentType.POST,
            metadata=metadata.model_dump(exclude_none=True),
            source_window=ctx.deps.window_label,
        )

        ctx.deps.resources.output.persist(doc)
        logger.info("Writer agent saved post (doc_id: %s)", doc.document_id)
        return WritePostResult(status="success", path=doc.document_id)

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str) -> ReadProfileResult:
        doc = ctx.deps.resources.output.read_document(DocumentType.PROFILE, author_uuid)
        content = doc.content if doc else "No profile exists yet."
        return ReadProfileResult(content=content)

    @agent.tool
    def write_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str, content: str) -> WriteProfileResult:
        doc = Document(
            content=content,
            type=DocumentType.PROFILE,
            metadata={"uuid": author_uuid},
            source_window=ctx.deps.window_label,
        )
        ctx.deps.resources.output.persist(doc)
        logger.info("Writer agent saved profile (doc_id: %s)", doc.document_id)
        return WriteProfileResult(status="success", path=doc.document_id)

    if enable_rag:

        @agent.tool
        async def search_media_tool(
            ctx: RunContext[WriterDeps], query: str, top_k: int = 5
        ) -> SearchMediaResult:
            """Search for relevant media (images, videos, audio) in the knowledge base.

            Args:
                query: Search query text describing the media you're looking for
                top_k: Number of results to return (default: 5)

            Returns:
                SearchMediaResult with matching media items

            """
            try:
                from egregora.rag import RAGQueryRequest, search

                # Execute RAG search
                request = RAGQueryRequest(text=query, top_k=top_k)
                response = await search(request)

                # Convert RAGHit results to MediaItem format
                media_items: list[MediaItem] = []
                for hit in response.hits:
                    # Extract media-specific metadata
                    metadata = hit.metadata or {}
                    media_type = metadata.get("media_type")
                    media_path = metadata.get("media_path")
                    original_filename = metadata.get("original_filename")

                    # Only include media documents
                    if media_type:
                        media_items.append(
                            MediaItem(
                                media_type=media_type,
                                media_path=media_path,
                                original_filename=original_filename,
                                description=hit.text[:500] if hit.text else None,
                                similarity=hit.score,
                            )
                        )

                logger.info(
                    "RAG media search returned %d results for query: %s", len(media_items), query[:50]
                )
                return SearchMediaResult(results=media_items)

            except (ConnectionError, TimeoutError) as exc:
                logger.warning("RAG backend unavailable for media search: %s", exc)
                return SearchMediaResult(results=[])
            except ValueError as exc:
                logger.warning("Invalid query for media search: %s", exc)
                return SearchMediaResult(results=[])
            except (AttributeError, KeyError) as exc:
                logger.error("Malformed response from RAG media search: %s", exc)
                return SearchMediaResult(results=[])

    @agent.tool
    def annotate_conversation_tool(
        ctx: RunContext[WriterDeps], parent_id: str, parent_type: str, commentary: str
    ) -> AnnotationResult:
        """Annotate a message or another annotation with commentary.

        Args:
            parent_id: The ID of the message or annotation being annotated
            parent_type: Must be exactly 'message' or 'annotation' (lowercase)
            commentary: Your commentary about the parent entity

        """
        if ctx.deps.resources.annotations_store is None:
            msg = "Annotation store is not configured"
            raise RuntimeError(msg)
        annotation = ctx.deps.resources.annotations_store.save_annotation(
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
            ctx: RunContext[WriterDeps], post_slug: str, title: str, summary: str
        ) -> BannerResult:
            # media_dir is not part of OutputSink, so we use output_format here
            banner_output_dir = ctx.deps.resources.output.media_dir / "images"

            result = generate_banner(post_title=title, post_summary=summary, slug=post_slug)

            if result.success and result.document:
                banner_path = save_media_asset(result.document, banner_output_dir)

                # Convert absolute path to web-friendly path
                # If using MkDocsAdapter, use its helper
                if hasattr(ctx.deps.output_sink, "get_media_url_path") and ctx.deps.ctx.site_root:
                    web_path = ctx.deps.output_sink.get_media_url_path(banner_path, ctx.deps.ctx.site_root)
                else:
                    # Fallback: assume standard structure /media/images/filename
                    web_path = f"/media/images/{banner_path.name}"

                return BannerResult(status="success", path=web_path)
            return BannerResult(status="failed", path=result.error)


# ============================================================================
# Context Building (RAG & Profiles)
# ============================================================================


@dataclass
class RagContext:
    """RAG query result with formatted text and metadata."""

    text: str
    records: list[dict[str, Any]]


def build_rag_context_for_prompt(  # noqa: PLR0913
    table_markdown: str,
    store: Any = None,
    client: Any = None,
    *,
    embedding_model: str = "",
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
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

    try:
        from egregora.rag import RAGQueryRequest, search

        # Use conversation content as search query (truncate if too long)
        query_text = table_markdown[:500]  # Use first 500 chars as query

        # Check cache if available
        cache_key = f"rag_context_{hash(query_text)}"
        if cache is not None:
            cached = cache.rag.get(cache_key)
            if cached is not None:
                logger.debug("RAG context cache hit")
                return cached

        # Execute RAG search
        import asyncio

        request = RAGQueryRequest(text=query_text, top_k=top_k)
        response = asyncio.run(search(request))

        if not response.hits:
            return ""

        # Build context from results
        parts = [
            "\n\n## Similar Posts (for context and inspiration):\n",
            "These are similar posts from previous conversations that might provide useful context:\n\n",
        ]

        for idx, hit in enumerate(response.hits, 1):
            similarity_pct = int(hit.score * 100)
            parts.append(f"### Similar Post {idx} (similarity: {similarity_pct}%)\n")
            parts.append(f"{hit.text[:500]}...\n\n")  # Truncate to 500 chars

        context = "".join(parts)

        # Cache the result
        if cache is not None:
            cache.rag.set(cache_key, context)

        logger.info("Built RAG context with %d similar posts", len(response.hits))
        return context

    except (ConnectionError, TimeoutError) as exc:
        logger.warning("RAG backend unavailable, continuing without context: %s", exc)
        return ""  # Non-critical: pipeline continues without RAG context
    except ValueError as exc:
        logger.warning("Invalid RAG query, continuing without context: %s", exc)
        return ""
    except (AttributeError, KeyError, TypeError) as exc:
        logger.error("Malformed RAG response, continuing without context: %s", exc)
        return ""


def _load_profiles_context(table: Table, profiles_dir: Path) -> str:
    """Load profiles for top active authors."""
    top_authors = get_active_authors(table, limit=20)
    if not top_authors:
        return ""
    logger.info("Loading profiles for %s active authors", len(top_authors))

    parts = [
        "\n\n## Active Participants (Profiles):\n",
        "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n",
    ]

    for author_uuid in top_authors:
        profile_content = read_profile(author_uuid, profiles_dir)
        parts.append(f"### Author: {author_uuid}\n")
        if profile_content:
            parts.append(f"{profile_content}\n\n")
        else:
            parts.append("(No profile yet - first appearance)\n\n")

    profiles_context = "".join(parts)
    logger.info("Profiles context: %s characters", len(profiles_context))
    return profiles_context


@dataclass
class WriterContext:
    """Encapsulates all contextual data required for the writer agent prompt."""

    conversation_xml: str
    rag_context: str
    profiles_context: str
    journal_memory: str
    active_authors: list[str]
    format_instructions: str
    custom_instructions: str
    source_context: str
    date_label: str
    pii_prevention: dict[str, Any] | None = None  # LLM-native PII prevention settings

    @property
    def template_context(self) -> dict[str, Any]:
        """Return context dictionary for Jinja template rendering."""
        return {
            "conversation_xml": self.conversation_xml,
            "rag_context": self.rag_context,
            "profiles_context": self.profiles_context,
            "journal_memory": self.journal_memory,
            "active_authors": ", ".join(self.active_authors),
            "format_instructions": self.format_instructions,
            "custom_instructions": self.custom_instructions,
            "source_context": self.source_context,
            "date": self.date_label,
            "enable_memes": False,
            "pii_prevention": self.pii_prevention,
        }


def _truncate_for_embedding(text: str, byte_limit: int = MAX_RAG_QUERY_BYTES) -> str:
    """Clamp markdown payloads before embedding to respect API limits."""
    encoded = text.encode("utf-8")
    if len(encoded) <= byte_limit:
        return text
    truncated = encoded[:byte_limit]
    truncated_text = truncated.decode("utf-8", errors="ignore").rstrip()
    logger.info(
        "Truncated RAG query markdown from %s bytes to %s bytes to fit embedding limits",
        len(encoded),
        byte_limit,
    )
    return truncated_text + "\n\n<!-- truncated for RAG query -->"


def _build_writer_context(  # noqa: PLR0913
    table_with_str_uuids: Table,
    resources: WriterResources,
    cache: PipelineCache,
    config: EgregoraConfig,
    window_label: str,
    adapter_content_summary: str,
    adapter_generation_instructions: str,
) -> WriterContext:
    """Collect contextual inputs used when rendering the writer prompt."""
    messages_table = table_with_str_uuids.to_pyarrow()
    conversation_xml = _build_conversation_xml(messages_table, resources.annotations_store)

    # Build RAG context if enabled
    if resources.retrieval_config.enabled:
        table_markdown = conversation_xml  # Use XML content for RAG query
        rag_context = build_rag_context_for_prompt(
            table_markdown,
            top_k=resources.retrieval_config.top_k,
            cache=cache,
        )
    else:
        rag_context = ""

    profiles_context = _load_profiles_context(table_with_str_uuids, resources.profiles_dir)
    journal_memory = _load_journal_memory(resources.output)
    active_authors = get_active_authors(table_with_str_uuids)

    format_instructions = resources.output.get_format_instructions()
    custom_instructions = config.writer.custom_instructions or ""
    if adapter_generation_instructions:
        custom_instructions = "\n\n".join(
            filter(None, [custom_instructions, adapter_generation_instructions])
        )

    # Build PII prevention context for LLM-native privacy protection
    pii_settings = config.privacy.pii_prevention.writer
    pii_prevention = None
    if pii_settings.enabled:
        pii_prevention = {
            "enabled": True,
            "scope": pii_settings.scope.value,
            "custom_definition": pii_settings.custom_definition
            if pii_settings.scope.value == "custom"
            else None,
            "apply_to_journals": pii_settings.apply_to_journals,
        }

    return WriterContext(
        conversation_xml=conversation_xml,
        rag_context=rag_context,
        profiles_context=profiles_context,
        journal_memory=journal_memory,
        active_authors=active_authors,
        format_instructions=format_instructions,
        custom_instructions=custom_instructions,
        source_context=adapter_content_summary,
        date_label=window_label,
        pii_prevention=pii_prevention,
    )


# ============================================================================
# Agent Runners & Orchestration
# ============================================================================


def _extract_thinking_content(messages: MessageHistory) -> list[str]:
    """Extract thinking/reasoning content from agent message history."""
    thinking_contents: list[str] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            thinking_contents.extend(part.content for part in message.parts if isinstance(part, ThinkingPart))
    return thinking_contents


def _extract_journal_content(messages: MessageHistory) -> str:
    """Extract journal content from agent message history."""
    journal_parts: list[str] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            journal_parts.extend(part.content for part in message.parts if isinstance(part, TextPart))
    return "\n\n".join(journal_parts).strip()


@dataclass(frozen=True)
class JournalEntry:
    """Represents a single entry in the intercalated journal log."""

    entry_type: str  # "thinking", "journal", "tool_call", "tool_return"
    content: str
    timestamp: datetime | None = None
    tool_name: str | None = None


def _create_tool_call_entry(part: ToolCallPart, timestamp) -> JournalEntry:
    """Create a journal entry for a tool call part.

    Args:
        part: Tool call part from message
        timestamp: Message timestamp

    Returns:
        Journal entry for the tool call

    """
    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
    return JournalEntry(
        JOURNAL_TYPE_TOOL_CALL,
        f"Tool: {part.tool_name}\nArguments:\n{args_str}",
        timestamp,
        part.tool_name,
    )


def _extract_intercalated_log(messages: MessageHistory) -> list[JournalEntry]:
    """Extract intercalated journal log preserving actual execution order."""
    entries: list[JournalEntry] = []

    for message in messages:
        timestamp = getattr(message, "timestamp", None)

        # Handle ModelResponse
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ThinkingPart):
                    entries.append(JournalEntry(JOURNAL_TYPE_THINKING, part.content, timestamp))
                elif isinstance(part, TextPart):
                    entries.append(JournalEntry(JOURNAL_TYPE_TEXT, part.content, timestamp))
                elif isinstance(part, ToolCallPart):
                    entries.append(_create_tool_call_entry(part, timestamp))
                elif isinstance(part, ToolReturnPart):
                    result_str = str(part.content) if hasattr(part, "content") else "No result"
                    entries.append(
                        JournalEntry(
                            JOURNAL_TYPE_TOOL_RETURN,
                            f"Result: {result_str}",
                            timestamp,
                            getattr(part, "tool_name", None),
                        )
                    )

        # Handle ModelRequest
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    entries.append(_create_tool_call_entry(part, timestamp))

    return entries


def _save_journal_to_file(  # noqa: PLR0913
    intercalated_log: list[JournalEntry],
    window_label: str,
    output_format: OutputSink,
    posts_published: int,
    profiles_updated: int,
    window_start: datetime,
    window_end: datetime,
    total_tokens: int = 0,
) -> str | None:
    """Save journal entry to markdown file."""
    if not intercalated_log:
        return None

    templates_dir = Path(__file__).resolve().parents[1] / TEMPLATES_DIR_NAME
    try:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape(enabled_extensions=())
        )
        template = env.get_template(JOURNAL_TEMPLATE_NAME)
    except TemplateNotFound as exc:
        logger.error("Journal template not found: %s", exc)
        return None
    except (OSError, PermissionError) as exc:
        logger.error("Cannot access template directory: %s", exc)
        return None

    now_utc = datetime.now(tz=UTC)
    window_start_iso = window_start.astimezone(UTC).isoformat()
    window_end_iso = window_end.astimezone(UTC).isoformat()
    journal_slug = now_utc.strftime("%Y-%m-%d-%H-%M-%S")
    try:
        journal_content = template.render(
            window_label=window_label,
            date=now_utc.strftime("%Y-%m-%d"),
            created=now_utc.isoformat(),
            posts_published=posts_published,
            profiles_updated=profiles_updated,
            entry_count=len(intercalated_log),
            intercalated_log=intercalated_log,
            window_start=window_start_iso,
            window_end=window_end_iso,
            total_tokens=total_tokens,
        )
    except TemplateError as exc:
        logger.error("Journal template rendering failed: %s", exc)
        return None
    except (TypeError, AttributeError) as exc:
        logger.error("Invalid template data for journal: %s", exc)
        return None
    journal_content = journal_content.replace("../media/", "/media/")

    try:
        doc = Document(
            content=journal_content,
            type=DocumentType.JOURNAL,
            metadata={
                "window_label": window_label,
                "window_start": window_start_iso,
                "window_end": window_end_iso,
                "date": now_utc.isoformat(),
                "created_at": now_utc.isoformat(),
                "slug": journal_slug,
                "nav_exclude": True,
                "hide": ["navigation"],
            },
            source_window=window_label,
        )
        output_format.persist(doc)
    except (OSError, IOError, PermissionError) as exc:
        logger.error("Failed to write journal to disk: %s", exc)
        return None
    except ValueError as exc:
        logger.error("Invalid journal document: %s", exc)
        return None
    logger.info("Saved journal entry: %s", doc.document_id)
    return doc.document_id


def _extract_tool_results(messages: MessageHistory) -> tuple[list[str], list[str]]:  # noqa: C901
    """Extract saved post and profile document IDs from agent message history."""
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    def _process_result(content: Any, tool_name: str | None) -> None:
        if isinstance(content, str):
            try:
                data = json.loads(content)
            except (ValueError, json.JSONDecodeError):
                return
        elif hasattr(content, "model_dump"):
            data = content.model_dump()
        elif isinstance(content, dict):
            data = content
        else:
            return

        if data.get("status") == "success" and "path" in data:
            path = data["path"]
            if tool_name == "write_post_tool" or "/posts/" in path:
                saved_posts.append(path)
            elif tool_name == "write_profile_tool" or "/profiles/" in path:
                saved_profiles.append(path)

    for message in messages:
        if hasattr(message, "parts"):
            for part in message.parts:
                if isinstance(part, ToolReturnPart):
                    _process_result(part.content, part.tool_name)
        elif hasattr(message, "kind") and message.kind == "tool-return":
            _process_result(message.content, getattr(message, "tool_name", None))

    return saved_posts, saved_profiles


def _prepare_deps(
    ctx: PipelineContext,
    window_start: datetime,
    window_end: datetime,
) -> WriterDeps:
    """Prepare writer dependencies from pipeline context."""
    window_label = f"{window_start:%Y-%m-%d %H:%M} to {window_end:%H:%M}"

    # Ensure output sink is initialized
    if not ctx.output_format:
        msg = "Output format not initialized in context"
        raise ValueError(msg)

    prompts_dir = ctx.site_root / ".egregora" / "prompts" if ctx.site_root else None

    return WriterDeps(
        ctx=ctx,
        window_start=window_start,
        window_end=window_end,
        window_label=window_label,
        prompts_dir=prompts_dir,
        quota=ctx.quota_tracker,
        usage_tracker=ctx.usage_tracker,
        rate_limit=ctx.rate_limit,
    )


def _validate_prompt_fits(
    prompt: str,
    model_name: str,
    config: EgregoraConfig,
    window_label: str,
) -> None:
    """Validate prompt fits within model context window limits."""
    max_prompt_tokens = getattr(config.pipeline, "max_prompt_tokens", 100_000)
    use_full_context_window = getattr(config.pipeline, "use_full_context_window", False)

    fits, estimated_tokens, _effective_limit = validate_prompt_fits(
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


@sleep_and_retry
@limits(calls=100, period=60)
def write_posts_with_pydantic_agent(
    *,
    prompt: str,
    config: EgregoraConfig,
    context: WriterDeps,
    test_model: AgentModel | None = None,
) -> tuple[list[str], list[str]]:
    """Execute the writer flow using Pydantic-AI agent tooling."""
    logger.info("Running writer via Pydantic-AI backend")

    model_name = test_model if test_model is not None else config.models.writer
    agent = Agent[WriterDeps, WriterAgentReturn](model=model_name, deps_type=WriterDeps)
    register_writer_tools(
        agent, enable_banner=is_banner_generation_available(), enable_rag=config.rag.enabled
    )

    _validate_prompt_fits(prompt, model_name, config, context.window_label)

    def _invoke_agent() -> Any:
        if context.resources.quota:
            context.resources.quota.reserve(1)
        return call_with_retries_sync(agent.run_sync, prompt, deps=context)

    try:
        result = retry_sync(_invoke_agent)
    except QuotaExceededError as exc:
        msg = (
            "LLM quota exceeded for this day. No additional posts can be generated "
            "until the usage window resets."
        )
        logger.exception(msg)
        raise RuntimeError(msg) from exc

    usage = result.usage()
    if context.resources.usage:
        context.resources.usage.record(usage)
    saved_posts, saved_profiles = _extract_tool_results(result.all_messages())
    intercalated_log = _extract_intercalated_log(result.all_messages())
    if not intercalated_log:
        fallback_content = _extract_journal_content(result.all_messages())
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
    _save_journal_to_file(
        intercalated_log,
        context.window_label,
        context.resources.output,
        len(saved_posts),
        len(saved_profiles),
        context.window_start,
        context.window_end,
        total_tokens=result.usage().total_tokens if result.usage() else 0,
    )

    logger.info(
        "Writer agent completed: period=%s posts=%d profiles=%d tokens=%d",
        context.window_label,
        len(saved_posts),
        len(saved_profiles),
        result.usage().total_tokens if result.usage() else 0,
    )

    return saved_posts, saved_profiles


def _render_writer_prompt(
    context: WriterContext,
    prompts_dir: Path | None,
) -> str:
    """Render the final writer prompt text."""
    return render_prompt(
        "writer.jinja",
        prompts_dir=prompts_dir,
        **context.template_context,
    )


def _cast_uuid_columns_to_str(table: Table) -> Table:
    """Ensure UUID-like columns are serialised to strings."""
    return table.mutate(
        event_id=table.event_id.cast(str),
        author_uuid=table.author_uuid.cast(str),
        thread_id=table.thread_id.cast(str),
        created_by_run=table.created_by_run.cast(str),
    )


def _check_writer_cache(
    cache: PipelineCache, signature: str, window_label: str, usage_tracker: UsageTracker | None = None
) -> dict[str, list[str]] | None:
    """Check L3 cache for cached writer results.

    Args:
        cache: Pipeline cache instance
        signature: Window signature for cache lookup
        window_label: Human-readable window label for logging
        usage_tracker: Optional usage tracker to record cache hits

    Returns:
        Cached result if found, None otherwise

    """
    if cache.should_refresh(CacheTier.WRITER):
        return None

    cached_result = cache.writer.get(signature)
    if cached_result:
        logger.info("⚡ [L3 Cache Hit] Skipping Writer LLM for window %s", window_label)
        if usage_tracker:
            # Record a cache hit (0 tokens) to track efficiency
            pass
    return cached_result


def _index_new_content_in_rag(
    resources: WriterResources,
    saved_posts: list[str],
    saved_profiles: list[str],
) -> None:
    """Index newly created content in RAG system.

    Args:
        resources: Writer resources including RAG configuration
        saved_posts: List of post identifiers that were created
        saved_profiles: List of profile identifiers that were updated

    """
    # Check if RAG is enabled and we have posts to index
    if not (resources.retrieval_config.enabled and saved_posts):
        return

    try:
        from egregora.data_primitives.document import DocumentType
        from egregora.rag import index_documents

        # Read the newly saved post documents
        docs: list[Document] = []
        for post_id in saved_posts:
            # Try to read the document from output format
            # The output format should have a way to read documents by identifier
            if hasattr(resources.output, "documents"):
                # Find the matching document in the output format's documents
                for doc in resources.output.documents():
                    if doc.type == DocumentType.POST and post_id in str(doc.metadata.get("slug", "")):
                        docs.append(doc)
                        break

        if docs:
            import asyncio

            asyncio.run(index_documents(docs))
            logger.info("Indexed %d new posts in RAG", len(docs))
        else:
            logger.debug("No new documents to index in RAG")

    except (ConnectionError, TimeoutError, RuntimeError) as exc:
        # Non-critical: Pipeline continues even if RAG indexing fails
        logger.warning("RAG backend unavailable for indexing, skipping: %s", exc)
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid document data for RAG indexing, skipping: %s", exc)
    except (OSError, PermissionError) as exc:
        logger.warning("Cannot access RAG storage, skipping indexing: %s", exc)


def write_posts_for_window(  # noqa: PLR0913 - Complex orchestration function
    table: Table,
    window_start: datetime,
    window_end: datetime,
    resources: WriterResources,
    config: EgregoraConfig,
    cache: PipelineCache,
    # These are extracted from pipeline context earlier and passed explicitly now
    adapter_content_summary: str = "",
    adapter_generation_instructions: str = "",
) -> dict[str, list[str]]:
    """Let LLM analyze window's messages, write 0-N posts, and update author profiles.

    This acts as the public entry point, orchestrating the setup and execution
    of the writer agent.
    """
    if table.count().execute() == 0:
        return {RESULT_KEY_POSTS: [], RESULT_KEY_PROFILES: []}

    # 1. Prepare Dependencies from resources
    window_label = f"{window_start:%Y-%m-%d %H:%M} to {window_end:%H:%M}"
    deps = WriterDeps(
        resources=resources,
        window_start=window_start,
        window_end=window_end,
        window_label=window_label,
    )

    # 2. Build Context & Calculate Signature (L3 Cache Check)
    table_with_str_uuids = _cast_uuid_columns_to_str(table)

    # Generate context early for both prompt and signature
    writer_context = _build_writer_context(
        table_with_str_uuids,
        resources,
        cache,
        config,
        window_label,
        adapter_content_summary,
        adapter_generation_instructions,
    )

    # Use PromptManager to get template content safely
    template_content = PromptManager.get_template_content(
        "writer.jinja", custom_prompts_dir=deps.resources.prompts_dir
    )

    # Calculate signature using data (XML) + logic (template) + engine
    signature = generate_window_signature(
        table_with_str_uuids, config, template_content, xml_content=writer_context.conversation_xml
    )

    # 4. Check L3 Cache
    cached_result = _check_writer_cache(cache, signature, deps.window_label, deps.resources.usage)
    if cached_result:
        return cached_result

    logger.info("Using Pydantic AI backend for writer")

    # Render prompt
    prompt = _render_writer_prompt(writer_context, deps.resources.prompts_dir)

    try:
        saved_posts, saved_profiles = write_posts_with_pydantic_agent(
            prompt=prompt,
            config=config,
            context=deps,
        )
    except PromptTooLargeError:
        raise
    except Exception as exc:
        msg = f"Writer agent failed for {deps.window_label}"
        logger.exception(msg)
        raise RuntimeError(msg) from exc

    # 6. Finalize Window
    resources.output.finalize_window(
        window_label=deps.window_label,
        posts_created=saved_posts,
        profiles_updated=saved_profiles,
        metadata=None,
    )

    # 7. Index Newly Created Content in RAG
    _index_new_content_in_rag(resources, saved_posts, saved_profiles)

    # 8. Update L3 Cache
    result_payload = {RESULT_KEY_POSTS: saved_posts, RESULT_KEY_PROFILES: saved_profiles}
    cache.writer.set(signature, result_payload)

    return result_payload


def load_format_instructions(site_root: Path | None, *, registry: OutputAdapterRegistry | None = None) -> str:
    """Load output format instructions for the writer agent."""
    registry = registry or create_default_output_registry()

    if site_root:
        detected_format = registry.detect_format(site_root)
        if detected_format:
            return detected_format.get_format_instructions()

    try:
        default_format = registry.get_format("mkdocs")
        return default_format.get_format_instructions()
    except KeyError:
        return ""


def get_top_authors(table: Table, limit: int = 20) -> list[str]:
    """Get top N active authors by message count."""
    author_counts = (
        table.filter(~table.author_uuid.cast("string").isin(["system", "egregora"]))
        .filter(table.author_uuid.notnull())
        .filter(table.author_uuid.cast("string") != "")
        .group_by("author_uuid")
        .aggregate(count=ibis._.count())
        .order_by(ibis.desc("count"))
        .limit(limit)
    )
    if author_counts.count().execute() == 0:
        return []
    return author_counts.author_uuid.cast("string").execute().tolist()
