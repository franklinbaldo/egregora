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
from collections.abc import AsyncGenerator
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
from egregora.agents.tools.annotations import AnnotationStore
from egregora.agents.tools.profiler import read_profile, write_profile
from egregora.agents.tools.rag import VectorStore, is_rag_available, query_media
from egregora.config.schema import EgregoraConfig
from egregora.database.streaming import stream_ibis
from egregora.utils.logfire_config import logfire_info, logfire_span
from egregora.utils.write_post import write_post

if TYPE_CHECKING:
    from egregora.agents.tools.annotations import AnnotationStore
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WriterRuntimeContext:
    """Runtime context for writer agent execution.

    MODERN (Phase 2): Bundles runtime parameters to reduce function signatures.
    Separates runtime data (paths, clients) from configuration (EgregoraConfig).

    Windows are identified by (start_time, end_time) tuple, not artificial IDs.
    This makes them stable across config changes and more meaningful for logging.
    """

    start_time: datetime
    end_time: datetime
    output_dir: Path
    profiles_dir: Path
    rag_dir: Path
    client: Any
    site_root: Path | None = None  # For custom prompt overrides in {site_root}/.egregora/prompts/
    annotations_store: AnnotationStore | None = None


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
    Results are extracted from the agent's message history instead of being
    tracked via mutation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    window_id: str
    output_dir: Path
    profiles_dir: Path
    rag_dir: Path
    batch_client: Any
    embedding_model: str
    retrieval_mode: str
    retrieval_nprobe: int | None
    retrieval_overfetch: int | None
    annotations_store: AnnotationStore | None


def _extract_thinking_content(messages: Any) -> list[str]:
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


def _extract_freeform_content(messages: Any) -> str:
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


def _extract_intercalated_log(messages: Any) -> list[JournalEntry]:  # noqa: C901
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
    output_dir: Path,
) -> Path | None:
    """Save journal entry with intercalated thinking, freeform, and tool usage to markdown file.

    Args:
        intercalated_log: List of journal entries in chronological order
        window_label: Human-readable window identifier (e.g., "2025-01-15 10:00 to 12:00")
        output_dir: Base output directory

    Returns:
        Path to saved journal file, or None if no content

    """
    # Skip if no content at all
    if not intercalated_log:
        return None

    # Create journal directory if it doesn't exist
    journal_dir = output_dir / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename from window label (sanitize for filesystem)
    safe_filename = window_label.replace(":", "-").replace(" ", "_")
    journal_path = journal_dir / f"journal_{safe_filename}.md"

    # Load template from templates directory
    templates_dir = Path(__file__).parent.parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape(enabled_extensions=())
    )
    template = env.get_template("journal.md.jinja")

    # Render journal content
    now_utc = datetime.now(tz=UTC)
    journal_content = template.render(
        window_label=window_label,
        date=now_utc.strftime("%Y-%m-%d"),
        created=now_utc.isoformat(),
        intercalated_log=intercalated_log,
    )

    # Write to file
    journal_path.write_text(journal_content, encoding="utf-8")
    logger.info("Saved journal entry to %s", journal_path)

    return journal_path


def _extract_tool_results(messages: Any) -> tuple[list[str], list[str]]:  # noqa: C901
    """Extract saved post and profile paths from agent message history.

    Parses the agent's tool call results to find WritePostResult and
    WriteProfileResult returns.

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        Tuple of (saved_posts, saved_profiles) as lists of file paths

    """
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    # Try to iterate through messages
    try:
        for message in messages:
            # Check if this is a tool return message
            if hasattr(message, "kind") and message.kind == "tool-return":
                # Parse the content - it might be JSON or a Pydantic model
                content = message.content
                if isinstance(content, str):
                    try:
                        data = json.loads(content)
                    except (json.JSONDecodeError, ValueError):
                        continue
                elif hasattr(content, "model_dump"):
                    data = content.model_dump()
                elif hasattr(content, "__dict__"):
                    data = vars(content)
                else:
                    data = content

                # Extract path from WritePostResult or WriteProfileResult
                if isinstance(data, dict):
                    if data.get("status") == "success" and "path" in data:
                        path = data["path"]
                        # Determine if it's a post or profile based on path
                        if "/posts/" in path or path.endswith(".md"):
                            saved_posts.append(path)
                        elif "/profiles/" in path:
                            saved_profiles.append(path)
    except (AttributeError, TypeError) as e:
        logger.debug("Could not parse tool results: %s", e)

    return (saved_posts, saved_profiles)


def _register_writer_tools(  # noqa: C901
    agent: Agent[WriterAgentState, WriterAgentReturn],
    *,
    enable_banner: bool = False,
    enable_rag: bool = False,
) -> None:
    """Attach tool implementations to the agent.

    Args:
        agent: The writer agent to register tools with
        enable_banner: Whether to register banner generation tool (requires GOOGLE_API_KEY)
        enable_rag: Whether to register RAG search tools (requires GOOGLE_API_KEY)

    """

    @agent.tool
    def write_post_tool(
        ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str
    ) -> WritePostResult:
        path = write_post(
            content=content, metadata=metadata.model_dump(exclude_none=True), output_dir=ctx.deps.output_dir
        )
        logger.info("Writer agent saved post %s", path)
        return WritePostResult(status="success", path=path)

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterAgentState], author_uuid: str) -> ReadProfileResult:
        content = read_profile(author_uuid, ctx.deps.profiles_dir)
        if not content:
            content = "No profile exists yet."
        return ReadProfileResult(content=content)

    @agent.tool
    def write_profile_tool(
        ctx: RunContext[WriterAgentState], author_uuid: str, content: str
    ) -> WriteProfileResult:
        path = write_profile(author_uuid, content, ctx.deps.profiles_dir)
        logger.info("Writer agent saved profile %s", path)
        return WriteProfileResult(status="success", path=path)

    if enable_rag:

        @agent.tool
        def search_media_tool(
            ctx: RunContext[WriterAgentState],
            query: str,
            media_types: list[str] | None = None,
            limit: int = 5,
        ) -> SearchMediaResult:
            store = VectorStore(ctx.deps.rag_dir / "chunks.parquet")
            results = query_media(
                query=query,
                store=store,
                media_types=media_types,
                top_k=limit,
                min_similarity=0.7,
                embedding_model=ctx.deps.embedding_model,
                retrieval_mode=ctx.deps.retrieval_mode,
                retrieval_nprobe=ctx.deps.retrieval_nprobe,
                retrieval_overfetch=ctx.deps.retrieval_overfetch,
            )
            items: list[MediaItem] = []
            for batch in stream_ibis(results, store._client, batch_size=100):
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
            annotation_id=annotation.get("annotation_id"),
            parent_id=annotation.get("parent_id"),
            parent_type=annotation.get("parent_type"),
        )

    if enable_banner:

        @agent.tool
        def generate_banner_tool(
            ctx: RunContext[WriterAgentState], post_slug: str, title: str, summary: str
        ) -> BannerResult:
            banner_path = generate_banner_for_post(
                post_title=title, post_summary=summary, output_dir=ctx.deps.output_dir, slug=post_slug
            )
            if banner_path:
                return BannerResult(status="success", path=str(banner_path))
            return BannerResult(status="failed", path=None)


def write_posts_with_pydantic_agent(  # noqa: PLR0915
    *,
    prompt: str,
    config: EgregoraConfig,
    context: WriterRuntimeContext,
    test_model: Any | None = None,
) -> tuple[list[str], list[str]]:
    """Execute the writer flow using Pydantic-AI agent tooling.

    MODERN (Phase 2): Reduced from 12 parameters to 3 (prompt, config, context).

    Args:
        prompt: System prompt for the writer agent
        config: Egregora configuration (models, RAG, writer settings)
        context: Runtime context (paths, client, period info)
        test_model: Optional test model for unit tests (bypasses config.models.writer)

    Returns:
        Tuple (saved_posts, saved_profiles)

    """
    logger.info("Running writer via Pydantic-AI backend")

    # Extract values from config and context (Phase 2)
    model_name = test_model if test_model is not None else config.models.writer
    embedding_model = config.models.embedding
    retrieval_mode = config.rag.mode
    retrieval_nprobe = config.rag.nprobe
    retrieval_overfetch = config.rag.overfetch

    # Always use structured tool calling mode (Pydantic AI with tools)
    agent = Agent[WriterAgentState, WriterAgentReturn](model=model_name, deps_type=WriterAgentState)
    _register_writer_tools(
        agent, enable_banner=is_banner_generation_available(), enable_rag=is_rag_available()
    )

    # Generate window identifier for logging
    window_label = f"{context.start_time:%Y-%m-%d %H:%M} to {context.end_time:%H:%M}"

    state = WriterAgentState(
        window_id=window_label,
        output_dir=context.output_dir,
        profiles_dir=context.profiles_dir,
        rag_dir=context.rag_dir,
        batch_client=context.client,
        embedding_model=embedding_model,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        annotations_store=context.annotations_store,
    )
    # Validate prompt fits in model's context window
    from egregora.agents.model_limits import validate_prompt_fits  # noqa: PLC0415

    # Extract token cap settings from pipeline config
    max_prompt_tokens = getattr(config.pipeline, "max_prompt_tokens", 100_000)
    use_full_context_window = getattr(config.pipeline, "use_full_context_window", False)

    fits, estimated_tokens, effective_limit = validate_prompt_fits(
        prompt,
        model_name,
        max_prompt_tokens=max_prompt_tokens,
        use_full_context_window=use_full_context_window,
    )
    if not fits:
        # Check if we're under the model's hard limit (may exceed 100k cap but still valid)
        from egregora.agents.model_limits import get_model_context_limit  # noqa: PLC0415

        model_limit = get_model_context_limit(model_name)
        model_effective_limit = int(model_limit * 0.9)  # 10% safety margin

        if estimated_tokens <= model_effective_limit:
            # Single large message exception: Exceeds 100k cap but fits in model
            logger.warning(
                "Prompt exceeds %dk cap (%d tokens) but fits in model limit (%d tokens) for %s (window: %s) - allowing as exception (likely single large message)",
                max_prompt_tokens // 1000,
                estimated_tokens,
                model_effective_limit,
                model_name,
                window_label,
            )
        else:
            # Hard limit exceeded - raise exception to trigger window splitting
            from egregora.agents.model_limits import PromptTooLargeError  # noqa: PLC0415

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

    with logfire_span("writer_agent", period=window_label, model=model_name):
        max_attempts = 3
        result = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = agent.run_sync(prompt, deps=state)
                break
            except Exception as exc:
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
        result_payload = getattr(result, "output", getattr(result, "data", result))

        # Extract tool results from message history
        saved_posts, saved_profiles = _extract_tool_results(result.all_messages())

        # Extract intercalated log (thinking, freeform, tool usage in order), save to journal
        intercalated_log = _extract_intercalated_log(result.all_messages())
        journal_path = _save_journal_to_file(intercalated_log, window_label, context.output_dir)

        usage = result.usage()
        logfire_info(
            "Writer agent completed",
            period=window_label,
            posts_created=len(saved_posts),
            profiles_updated=len(saved_profiles),
            journal_saved=journal_path is not None,
            journal_entries=len(intercalated_log),
            journal_thinking_entries=sum(1 for e in intercalated_log if e.entry_type == "thinking"),
            journal_freeform_entries=sum(1 for e in intercalated_log if e.entry_type == "freeform"),
            journal_tool_calls=sum(1 for e in intercalated_log if e.entry_type == "tool_call"),
            # Standard token counts
            tokens_total=usage.total_tokens if usage else 0,
            tokens_input=usage.input_tokens if usage else 0,
            tokens_output=usage.output_tokens if usage else 0,
            # Cache token counts (prompt caching)
            tokens_cache_write=usage.cache_write_tokens if usage else 0,
            tokens_cache_read=usage.cache_read_tokens if usage else 0,
            # Audio token counts (for multimodal models)
            tokens_input_audio=usage.input_audio_tokens if usage else 0,
            tokens_cache_audio_read=usage.cache_audio_read_tokens if usage else 0,
            # Thinking/reasoning tokens (from details dict - provider-specific)
            tokens_thinking=usage.details.get("thinking_tokens", 0) if usage else 0,
            tokens_reasoning=usage.details.get("reasoning_tokens", 0) if usage else 0,
            # Raw details for any other model-specific metrics
            usage_details=usage.details if usage else {},
        )
        logger.info("Writer agent finished with summary: %s", getattr(result_payload, "summary", None))
        record_dir = os.environ.get("EGREGORA_LLM_RECORD_DIR")
        if record_dir:
            output_path = Path(record_dir).expanduser()
            output_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
            # Use start time for filename
            filename = output_path / f"writer-{context.start_time:%Y%m%d_%H%M%S}-{timestamp}.json"
            try:
                payload = ModelMessagesTypeAdapter.dump_json(result.all_messages())
                filename.write_bytes(payload)
                logger.info("Recorded writer agent conversation to %s", filename)
            except (OSError, TypeError, ValueError, AttributeError) as record_exc:
                logger.warning("Failed to persist writer agent messages: %s", record_exc)
    return (saved_posts, saved_profiles)


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
        agent: Agent,
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
    test_model: Any | None = None,
) -> WriterStreamResult:
    """Execute writer with streaming output.

    MODERN (Phase 2): Reduced from 12 parameters to 3 (prompt, config, context).

    Args:
        prompt: System prompt for the writer agent
        config: Egregora configuration (models, RAG, writer settings)
        context: Runtime context (paths, client, period info)
        test_model: Optional test model for unit tests (bypasses config.models.writer)

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
        output_dir=context.output_dir,
        profiles_dir=context.profiles_dir,
        rag_dir=context.rag_dir,
        batch_client=context.client,
        embedding_model=embedding_model,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        annotations_store=context.annotations_store,
    )
    return WriterStreamResult(agent, state, prompt, context, model_name)
