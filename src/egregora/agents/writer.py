"""Pydantic-AI powered writer agent.

This module implements the writer workflow using Pydantic-AI.
It exposes ``write_posts_for_window`` which routes the LLM conversation through a
``pydantic_ai.Agent`` instance.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
from ibis.expr.types import Table
from jinja2 import Environment, FileSystemLoader, select_autoescape
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

from egregora.agents.banner import generate_banner_for_post, is_banner_generation_available
from egregora.agents.formatting import (
    _build_conversation_markdown_table,
    _load_journal_memory,
)
from egregora.agents.model_limits import PromptTooLargeError
from egregora.agents.shared.rag import (
    VectorStore,
    embed_query_text,
    index_documents_for_rag,
    is_rag_available,
    query_media,
)
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import OutputSink, UrlContext, UrlConvention
from egregora.knowledge.profiles import get_active_authors, read_profile
from egregora.output_adapters import create_output_format, output_registry
from egregora.output_adapters.mkdocs import MkDocsAdapter
from egregora.resources.prompts import render_prompt
from egregora.utils.batch import call_with_retries_sync
from egregora.utils.metrics import UsageTracker
from egregora.utils.quota import QuotaExceededError, QuotaTracker
from egregora.utils.rate_limit import AsyncRateLimit
from egregora.utils.retry import RetryPolicy, retry_sync

if TYPE_CHECKING:
    from google import genai

    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)
MAX_RAG_QUERY_BYTES = 30000

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
class WriterDeps:
    """Immutable dependencies passed to agent tools.

    Replaces WriterAgentContext and WriterAgentState with a single,
    simplified structure wrapping the PipelineContext.
    """

    ctx: PipelineContext
    window_start: datetime
    window_end: datetime
    window_label: str
    prompts_dir: Path | None

    quota: QuotaTracker | None
    usage_tracker: UsageTracker | None
    rate_limit: AsyncRateLimit | None

    @property
    def output_format(self) -> OutputSink:
        if self.ctx.output_format is None:
            message = "Output format not initialized in context"
            raise RuntimeError(message)
        return self.ctx.output_format

    @property
    def url_convention(self) -> UrlConvention:
        return self.output_format.url_convention

    @property
    def url_context(self) -> UrlContext:
        if self.ctx.url_context is None:
            # Fallback if not set, though it should be
            storage_root = self.ctx.site_root if self.ctx.site_root else self.ctx.output_dir
            return UrlContext(base_url="", site_prefix="", base_path=storage_root)
        return self.ctx.url_context


# ============================================================================
# Tool Definitions
# ============================================================================


def register_writer_tools(  # noqa: C901
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
        url = ctx.deps.url_convention.canonical_url(doc, ctx.deps.url_context)
        ctx.deps.output_format.persist(doc)
        logger.info("Writer agent saved post at URL: %s (doc_id: %s)", url, doc.document_id)
        return WritePostResult(status="success", path=url)

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str) -> ReadProfileResult:
        doc = ctx.deps.output_format.get(DocumentType.PROFILE, author_uuid)
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
        url = ctx.deps.url_convention.canonical_url(doc, ctx.deps.url_context)
        ctx.deps.output_format.persist(doc)
        logger.info("Writer agent saved profile at URL: %s (doc_id: %s)", url, doc.document_id)
        return WriteProfileResult(status="success", path=url)

    if enable_rag:

        @agent.tool
        def search_media_tool(
            ctx: RunContext[WriterDeps],
            query: str,
            media_types: list[str] | None = None,
            limit: int = 5,
        ) -> SearchMediaResult:
            if not ctx.deps.ctx.rag_store:
                return SearchMediaResult(results=[])

            results = query_media(
                query=query,
                store=ctx.deps.ctx.rag_store,
                media_types=media_types,
                top_k=limit,
                min_similarity_threshold=0.7,
                embedding_model=ctx.deps.ctx.embedding_model,
                retrieval_mode=ctx.deps.ctx.retrieval_mode,
                retrieval_nprobe=ctx.deps.ctx.retrieval_nprobe,
                retrieval_overfetch=ctx.deps.ctx.retrieval_overfetch,
            )
            media_df = results.execute()
            items = [MediaItem(**row) for row in media_df.to_dict("records")]
            return SearchMediaResult(results=items)

    @agent.tool
    def annotate_conversation_tool(
        ctx: RunContext[WriterDeps], parent_id: str, parent_type: str, commentary: str
    ) -> AnnotationResult:
        if ctx.deps.ctx.annotations_store is None:
            msg = "Annotation store is not configured"
            raise RuntimeError(msg)
        annotation = ctx.deps.ctx.annotations_store.save_annotation(
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
            banner_output_dir = ctx.deps.output_format.media_dir / "images"
            banner_path = generate_banner_for_post(
                post_title=title, post_summary=summary, output_dir=banner_output_dir, slug=post_slug
            )
            if banner_path:
                return BannerResult(status="success", path=str(banner_path))
            return BannerResult(status="failed", path=None)


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
    store: VectorStore,
    client: genai.Client,
    *,
    embedding_model: str,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    top_k: int = 5,
) -> str:
    """Build a lightweight RAG context string from the conversation markdown."""
    if not table_markdown.strip():
        return ""

    # Simple query strategy for prompt context
    query_text = _truncate_for_embedding(table_markdown)
    query_vector = embed_query_text(query_text, model=embedding_model)
    search_results = store.search(
        query_vec=query_vector,
        top_k=top_k,
        min_similarity_threshold=0.7,
        mode=retrieval_mode,
        nprobe=retrieval_nprobe,
        overfetch=retrieval_overfetch,
    )
    results_df = search_results.execute()
    if getattr(results_df, "empty", False):
        logger.info("Writer RAG: no similar posts found for query")
        return ""
    records = results_df.to_dict("records")
    if not records:
        return ""
    lines = [
        "## Related Previous Posts (for continuity and linking):",
        "You can reference these posts in your writing to maintain conversation continuity.\n",
    ]
    for row in records:
        title = row.get("post_title") or "Untitled"
        post_date = row.get("post_date") or ""
        snippet = (row.get("content") or "")[:400]
        tags = row.get("tags") or []
        similarity = row.get("similarity")
        lines.append(f"### [{title}] ({post_date})")
        lines.append(f"{snippet}...")
        lines.append(f"- Tags: {(', '.join(tags) if tags else 'none')}")
        if similarity is not None:
            lines.append(f"- Similarity: {float(similarity):.2f}")
        lines.append("")
    return "\n".join(lines).strip()


def _load_profiles_context(table: Table, profiles_dir: Path) -> str:
    """Load profiles for top active authors."""
    top_authors = get_active_authors(table, limit=20)
    if not top_authors:
        return ""
    logger.info("Loading profiles for %s active authors", len(top_authors))
    profiles_context = "\n\n## Active Participants (Profiles):\n"
    profiles_context += "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n"
    for author_uuid in top_authors:
        profile_content = read_profile(author_uuid, profiles_dir)
        if profile_content:
            profiles_context += f"### Author: {author_uuid}\n"
            profiles_context += f"{profile_content}\n\n"
        else:
            profiles_context += f"### Author: {author_uuid}\n"
            profiles_context += "(No profile yet - first appearance)\n\n"
    logger.info("Profiles context: %s characters", len(profiles_context))
    return profiles_context


@dataclass
class WriterPromptContext:
    """Values used to populate the writer prompt template."""

    conversation_md: str
    rag_context: str
    profiles_context: str
    journal_memory: str
    active_authors: list[str]


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


def _build_writer_prompt_context(
    table_with_str_uuids: Table,
    ctx: PipelineContext,
) -> WriterPromptContext:
    """Collect contextual inputs used when rendering the writer prompt."""
    messages_table = table_with_str_uuids.to_pyarrow()
    conversation_md = _build_conversation_markdown_table(messages_table, ctx.annotations_store)

    if ctx.enable_rag and ctx.rag_store:
        rag_context = build_rag_context_for_prompt(
            conversation_md,
            ctx.rag_store,
            ctx.client,
            embedding_model=ctx.embedding_model,
            retrieval_mode=ctx.retrieval_mode,
            retrieval_nprobe=ctx.retrieval_nprobe,
            retrieval_overfetch=ctx.retrieval_overfetch,
        )
    else:
        rag_context = ""

    profiles_context = _load_profiles_context(table_with_str_uuids, ctx.profiles_dir)
    journal_memory = _load_journal_memory(ctx.output_dir)
    active_authors = get_active_authors(table_with_str_uuids)

    return WriterPromptContext(
        conversation_md=conversation_md,
        rag_context=rag_context,
        profiles_context=profiles_context,
        journal_memory=journal_memory,
        active_authors=active_authors,
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


def _extract_intercalated_log(messages: MessageHistory) -> list[JournalEntry]:  # noqa: C901
    """Extract intercalated journal log preserving actual execution order."""
    entries: list[JournalEntry] = []

    for message in messages:
        # Handle ModelResponse
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ThinkingPart):
                    entries.append(
                        JournalEntry("thinking", part.content, getattr(message, "timestamp", None))
                    )
                elif isinstance(part, TextPart):
                    entries.append(JournalEntry("journal", part.content, getattr(message, "timestamp", None)))
                elif isinstance(part, ToolCallPart):
                    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
                    entries.append(
                        JournalEntry(
                            "tool_call",
                            f"Tool: {part.tool_name}\nArguments:\n{args_str}",
                            getattr(message, "timestamp", None),
                            part.tool_name,
                        )
                    )
                elif isinstance(part, ToolReturnPart):
                    result_str = str(part.content) if hasattr(part, "content") else "No result"
                    entries.append(
                        JournalEntry(
                            "tool_return",
                            f"Result: {result_str}",
                            getattr(message, "timestamp", None),
                            getattr(part, "tool_name", None),
                        )
                    )

        # Handle ModelRequest
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
                    entries.append(
                        JournalEntry(
                            "tool_call",
                            f"Tool: {part.tool_name}\nArguments:\n{args_str}",
                            getattr(message, "timestamp", None),
                            part.tool_name,
                        )
                    )

    return entries


def _save_journal_to_file(
    intercalated_log: list[JournalEntry],
    window_label: str,
    output_format: OutputSink,
    posts_published: int,
    profiles_updated: int,
    window_start: datetime,
    window_end: datetime,
) -> str | None:
    """Save journal entry to markdown file."""
    if not intercalated_log:
        return None

    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    try:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape(enabled_extensions=())
        )
        template = env.get_template("journal.md.jinja")
    except Exception:
        logger.exception("Failed to load journal template")
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
        )
    except Exception:
        logger.exception("Failed to render journal template")
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
    except Exception:
        logger.exception("Failed to write journal")
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
        storage_root = ctx.site_root if ctx.site_root else ctx.output_dir
        format_type = ctx.config.output.format

        if format_type == "mkdocs":
            output_format = MkDocsAdapter()
            url_context = ctx.url_context or UrlContext(base_url="", site_prefix="", base_path=storage_root)
            output_format.initialize(site_root=storage_root, url_context=url_context)
        else:
            output_format = create_output_format(storage_root, format_type=format_type)

        # We need a new context with this format
        ctx = ctx.with_output_format(output_format)

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
        agent, enable_banner=is_banner_generation_available(), enable_rag=is_rag_available()
    )

    _validate_prompt_fits(prompt, model_name, config, context.window_label)

    retry_policy = RetryPolicy()

    def _invoke_agent() -> AgentRunResult:
        if context.rate_limit:
            asyncio.run(context.rate_limit.acquire())
        if context.quota:
            context.quota.reserve(1)
        return call_with_retries_sync(agent.run_sync, prompt, deps=context)

    try:
        result = retry_sync(_invoke_agent, retry_policy)
    except QuotaExceededError as exc:
        msg = (
            "LLM quota exceeded for this day. No additional posts can be generated "
            "until the usage window resets."
        )
        logger.error(msg)
        raise RuntimeError(msg) from exc

    usage = result.usage()
    if context.usage_tracker:
        context.usage_tracker.record(usage)
    saved_posts, saved_profiles = _extract_tool_results(result.all_messages())
    intercalated_log = _extract_intercalated_log(result.all_messages())
    if not intercalated_log:
        fallback_content = _extract_journal_content(result.all_messages())
        if fallback_content:
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
        context.output_format,
        len(saved_posts),
        len(saved_profiles),
        context.window_start,
        context.window_end,
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
    prompt_context: WriterPromptContext,
    ctx: PipelineContext,
    deps: WriterDeps,
) -> str:
    """Render the final writer prompt text."""
    format_instructions = ctx.output_format.get_format_instructions() if ctx.output_format else ""
    custom_instructions = ctx.config.writer.custom_instructions or ""
    adapter_instructions = _adapter_generation_instructions(ctx)
    if adapter_instructions:
        custom_instructions = "\n\n".join(filter(None, [custom_instructions, adapter_instructions]))
    source_context = _adapter_content_summary(ctx)

    return render_prompt(
        "writer.jinja",
        prompts_dir=deps.prompts_dir,
        date=deps.window_label,
        markdown_table=prompt_context.conversation_md,
        active_authors=", ".join(prompt_context.active_authors),
        custom_instructions=custom_instructions,
        format_instructions=format_instructions,
        profiles_context=prompt_context.profiles_context,
        rag_context=prompt_context.rag_context,
        journal_memory=prompt_context.journal_memory,
        source_context=source_context,
        enable_memes=False,
    )


def _adapter_content_summary(ctx: PipelineContext) -> str:
    adapter = getattr(ctx, "adapter", None)
    if adapter is None:
        return ""

    summary: str | None = ""
    try:
        summary = getattr(adapter, "content_summary", "")
    except Exception:
        logger.debug("Adapter %s lacks content_summary", adapter)
        summary = ""

    if callable(summary):
        try:
            summary = summary()
        except Exception:
            logger.exception("Failed to evaluate adapter content summary")
            summary = ""

    return (summary or "").strip()


def _adapter_generation_instructions(ctx: PipelineContext) -> str:
    adapter = getattr(ctx, "adapter", None)
    if adapter is None:
        return ""

    instructions = getattr(adapter, "generation_instructions", "")
    if callable(instructions):
        try:
            instructions = instructions()
        except Exception:
            logger.exception("Failed to evaluate adapter generation instructions")
            instructions = ""
    return (instructions or "").strip()


def _cast_uuid_columns_to_str(table: Table) -> Table:
    """Ensure UUID-like columns are serialised to strings."""
    return table.mutate(
        event_id=table.event_id.cast(str),
        author_uuid=table.author_uuid.cast(str),
        thread_id=table.thread_id.cast(str),
        created_by_run=table.created_by_run.cast(str),
    )


def write_posts_for_window(
    table: Table,
    window_start: datetime,
    window_end: datetime,
    ctx: PipelineContext,
) -> dict[str, list[str]]:
    """Let LLM analyze window's messages, write 0-N posts, and update author profiles.

    This acts as the public entry point, orchestrating the setup and execution
    of the writer agent.
    """
    if table.count().execute() == 0:
        return {"posts": [], "profiles": []}

    logger.info("Using Pydantic AI backend for writer")

    # Prepare dependencies
    deps = _prepare_deps(ctx, window_start, window_end)

    # Prepare prompt context
    table_with_str_uuids = _cast_uuid_columns_to_str(table)
    prompt_context = _build_writer_prompt_context(table_with_str_uuids, ctx)

    # Render prompt
    prompt = _render_writer_prompt(prompt_context, ctx, deps)

    try:
        saved_posts, saved_profiles = write_posts_with_pydantic_agent(
            prompt=prompt,
            config=ctx.config,
            context=deps,
        )
    except PromptTooLargeError:
        raise
    except Exception as exc:
        msg = f"Writer agent failed for {deps.window_label}"
        logger.exception(msg)
        raise RuntimeError(msg) from exc

    # Finalize
    if ctx.output_format:
        ctx.output_format.finalize_window(
            window_label=deps.window_label,
            posts_created=saved_posts,
            profiles_updated=saved_profiles,
            metadata=None,
        )

    # Index newly created content
    if ctx.enable_rag and ctx.rag_store and ctx.output_format and (saved_posts or saved_profiles):
        try:
            indexed_count = index_documents_for_rag(
                ctx.output_format,
                ctx.rag_store.parquet_path.parent,  # Use parent dir
                ctx.storage,
                embedding_model=ctx.embedding_model,
            )
            if indexed_count > 0:
                logger.info("Indexed %d new/changed documents in RAG after writing", indexed_count)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to update RAG index after writing: %s", e)

    return {"posts": saved_posts, "profiles": saved_profiles}


def load_format_instructions(site_root: Path | None) -> str:
    """Load output format instructions for the writer agent."""
    if site_root:
        detected_format = output_registry.detect_format(site_root)
        if detected_format:
            return detected_format.get_format_instructions()

    try:
        default_format = output_registry.get_format("mkdocs")
        return default_format.get_format_instructions()
    except KeyError:
        return ""


def get_top_authors(table: Table, limit: int = 20) -> list[str]:
    """Get top N active authors by message count."""
    author_counts = (
        table.filter(~table.author_uuid.cast("string").isin(["system", "egregora"]))
        .filter(table.author_uuid.notna())
        .filter(table.author_uuid.cast("string") != "")
        .group_by("author_uuid")
        .aggregate(count=ibis._.count())
        .order_by(ibis.desc("count"))
        .limit(limit)
    )
    if author_counts.count().execute() == 0:
        return []
    return author_counts.author_uuid.cast("string").execute().tolist()
