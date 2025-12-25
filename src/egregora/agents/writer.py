"""Pydantic-AI powered writer agent.

This module implements the writer workflow using Pydantic-AI.
It acts as the Composition Root for the agent, assembling core tools and
capabilities before executing the conversation through a ``pydantic_ai.Agent``.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import ibis.common.exceptions
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.exceptions import TemplateError, TemplateNotFound
from pydantic_ai import UsageLimits
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from ratelimit import limits, sleep_and_retry
from tenacity import Retrying

from egregora.agents.exceptions import (
    JournalFileSystemError,
    JournalTemplateError,
    WriterAgentExecutionError,
)
from egregora.agents.types import (
    PromptTooLargeError,
    WriterDeps,
    WriterResources,
)
from egregora.agents.writer_context import (
    RESULT_KEY_POSTS,
    RESULT_KEY_PROFILES,
    WriterContext,
    WriterContextParams,
    WriterDepsParams,
    build_context_and_signature,
    check_writer_cache,
    index_new_content_in_rag,
    prepare_writer_dependencies,
)
from egregora.agents.writer_helpers import (
    process_tool_result,
)
from egregora.agents.writer_setup import (
    create_writer_model,
    setup_writer_agent,
)
from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters import OutputSinkRegistry, create_default_output_registry
from egregora.resources.prompts import render_prompt
from egregora.utils.cache import PipelineCache
from egregora.utils.retry import RETRY_IF, RETRY_STOP, RETRY_WAIT

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.config.settings import EgregoraConfig
    from egregora.data_primitives.protocols import OutputSink
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)

# Constants
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

# Type aliases for improved type safety
MessageHistory = Sequence[ModelRequest | ModelResponse]
LLMClient = Any
AgentModel = Any


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


def _create_tool_call_entry(part: ToolCallPart, timestamp: datetime | None) -> JournalEntry:
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


def _process_response_part(part: Any, timestamp: datetime | None) -> JournalEntry | None:
    """Convert a message part to a journal entry."""
    if isinstance(part, ThinkingPart):
        return JournalEntry(JOURNAL_TYPE_THINKING, part.content, timestamp)
    if isinstance(part, TextPart):
        return JournalEntry(JOURNAL_TYPE_TEXT, part.content, timestamp)
    if isinstance(part, ToolCallPart):
        return _create_tool_call_entry(part, timestamp)
    if isinstance(part, ToolReturnPart):
        result_str = str(part.content) if hasattr(part, "content") else "No result"
        return JournalEntry(
            JOURNAL_TYPE_TOOL_RETURN,
            f"Result: {result_str}",
            timestamp,
            getattr(part, "tool_name", None),
        )
    return None


def _extract_intercalated_log(messages: MessageHistory) -> list[JournalEntry]:
    """Extract intercalated journal log preserving actual execution order."""
    entries: list[JournalEntry] = []

    for message in messages:
        timestamp = getattr(message, "timestamp", None)

        if isinstance(message, ModelResponse):
            entries.extend(
                filter(
                    None,
                    (_process_response_part(part, timestamp) for part in message.parts),
                )
            )

        elif isinstance(message, ModelRequest):
            entries.extend(
                _create_tool_call_entry(part, timestamp)
                for part in message.parts
                if isinstance(part, ToolCallPart)
            )

    return entries


@dataclass
class JournalEntryParams:
    """Parameters for saving a journal entry."""

    intercalated_log: list[JournalEntry]
    window_label: str
    output_format: OutputSink
    posts_published: int
    profiles_updated: int
    window_start: datetime
    window_end: datetime
    total_tokens: int = 0


def _save_journal_to_file(params: JournalEntryParams) -> str:
    """Save journal entry to markdown file."""
    intercalated_log = params.intercalated_log
    if not intercalated_log:
        return ""

    templates_dir = Path(__file__).resolve().parents[1] / TEMPLATES_DIR_NAME
    now_utc = datetime.now(tz=UTC)
    window_start_iso = params.window_start.astimezone(UTC).isoformat()
    window_end_iso = params.window_end.astimezone(UTC).isoformat()
    journal_slug = now_utc.strftime("%Y-%m-%d-%H-%M-%S")
    journal_path_str = f"journal/{journal_slug}.md"

    try:
        # Security: Enable autoescape for markdown/jinja templates to prevent XSS in journals
        # This ensures that if the LLM outputs <script> tags, they are escaped in the rendered markdown
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "htm", "xml", "jinja", "md"]),
        )
        template = env.get_template(JOURNAL_TEMPLATE_NAME)
        journal_content = template.render(
            window_label=params.window_label,
            date=now_utc.strftime("%Y-%m-%d"),
            created=now_utc.isoformat(),
            posts_published=params.posts_published,
            profiles_updated=params.profiles_updated,
            entry_count=len(intercalated_log),
            intercalated_log=intercalated_log,
            window_start=window_start_iso,
            window_end=window_end_iso,
            total_tokens=params.total_tokens,
        )

        doc = Document(
            content=journal_content,
            type=DocumentType.JOURNAL,
            metadata={
                "window_label": params.window_label,
                "window_start": window_start_iso,
                "window_end": window_end_iso,
                "date": now_utc.strftime("%Y-%m-%d %H:%M"),
                "created_at": now_utc.strftime("%Y-%m-%d %H:%M"),
                "slug": journal_slug,
                "nav_exclude": True,
                "hide": ["navigation"],
            },
            source_window=params.window_label,
        )
        params.output_format.persist(doc)
        logger.info("Saved journal entry: %s", doc.document_id)
        return doc.document_id
    except (TemplateNotFound, TemplateError) as e:
        raise JournalTemplateError(template_name=JOURNAL_TEMPLATE_NAME, reason=str(e)) from e
    except (OSError, PermissionError) as e:
        raise JournalFileSystemError(path=journal_path_str, reason=str(e)) from e
    except (TypeError, AttributeError, ValueError) as e:
        # Catching other potential issues during doc creation
        msg = f"Invalid data for journal: {e}"
        logger.exception(msg)
        raise JournalFileSystemError(path=journal_path_str, reason=msg) from e


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


def _extract_tool_results(messages: MessageHistory) -> tuple[list[str], list[str]]:
    """Extract saved post and profile document IDs from agent message history."""
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    for message in messages:
        _extract_from_message(message, saved_posts, saved_profiles)

    return saved_posts, saved_profiles


def _prepare_deps(
    ctx: PipelineContext,
    window_start: datetime,
    window_end: datetime,
) -> WriterDeps:
    """Prepare writer dependencies from pipeline context."""
    # Ensure output sink is initialized
    if not ctx.output_format:
        msg = "Output format not initialized in context"
        raise ValueError(msg)

    prompts_dir = ctx.site_root / ".egregora" / "prompts" if ctx.site_root else None

    # Construct WriterResources using existing context
    resources = WriterResources(
        output=ctx.output_format,
        annotations_store=ctx.annotations_store,
        storage=ctx.storage,
        task_store=getattr(ctx, "task_store", None),
        embedding_model=ctx.config.models.embedding,
        retrieval_config=ctx.config.rag,
        profiles_dir=ctx.site_root / "profiles" if ctx.site_root else None,
        journal_dir=ctx.site_root / "journal" if ctx.site_root else None,
        prompts_dir=prompts_dir,
        client=getattr(ctx, "client", None),
        usage=ctx.usage_tracker,
        output_registry=getattr(ctx, "output_registry", None),
        run_id=ctx.run_id,
    )

    return prepare_writer_dependencies(
        WriterDepsParams(
            window_start=window_start,
            window_end=window_end,
            resources=resources,
            model_name=ctx.config.models.writer,
        )
    )


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

    model = await create_writer_model(config, context, prompt, test_model)
    agent = setup_writer_agent(model, prompt, config)

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
            attempt_num = attempt.retry_state.attempt_number
            logger.info(
                "🖊️  [Writer] Starting LLM call for %s (attempt %d/%d)...",
                context.window_label,
                attempt_num,
                RETRY_STOP.max_attempt_number if hasattr(RETRY_STOP, "max_attempt_number") else 3,
            )
            # Execute model directly without tools
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
    if intercalated_log:
        _save_journal_to_file(
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


async def _execute_writer_with_error_handling(
    prompt: str,
    config: EgregoraConfig,
    deps: WriterDeps,
) -> tuple[list[str], list[str]]:
    """Execute writer agent with proper error handling.

    Returns:
        Tuple of (saved_posts, saved_profiles)

    Raises:
        PromptTooLargeError: If prompt exceeds model context window (propagated unchanged)
        WriterAgentExecutionError: For other agent failures (wrapped with context)

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

        msg = f"Writer agent failed for {deps.window_label}"
        logger.exception(msg)
        raise WriterAgentExecutionError(window_label=deps.window_label, reason=str(exc)) from exc


@dataclass
class WriterFinalizationParams:
    """Parameters for finalizing writer results."""

    saved_posts: list[str]
    saved_profiles: list[str]
    resources: WriterResources
    deps: WriterDeps
    cache: PipelineCache
    signature: str


def _finalize_writer_results(params: WriterFinalizationParams) -> dict[str, list[str]]:
    """Finalize window results: output, RAG indexing, and caching.

    Returns:
        Result payload dict with 'posts' and 'profiles' keys

    """
    # Finalize output adapter
    params.resources.output.finalize_window(
        window_label=params.deps.window_label,
        profiles_updated=params.saved_profiles,
        metadata=None,
    )

    # Index newly created content in RAG
    index_new_content_in_rag(params.resources, params.saved_posts, params.saved_profiles)

    # Update L3 cache
    result_payload = {RESULT_KEY_POSTS: params.saved_posts, RESULT_KEY_PROFILES: params.saved_profiles}
    params.cache.writer.set(params.signature, result_payload)

    return result_payload


@dataclass
class WindowProcessingParams:
    """Parameters for processing a window of messages."""

    table: Table
    window_start: datetime
    window_end: datetime
    resources: WriterResources
    config: EgregoraConfig
    cache: PipelineCache
    adapter_content_summary: str = ""
    adapter_generation_instructions: str = ""
    run_id: str | None = None
    is_demo: bool = False


async def write_posts_for_window(params: WindowProcessingParams) -> dict[str, list[str]]:
    """Let LLM analyze window's messages, write 0-N posts, and update author profiles.

    This acts as the public entry point, orchestrating the setup and execution
    of the writer agent.
    """
    if params.is_demo:
        logger.info("🤖 Demo mode: Skipping writer agent and returning mock data.")
        return {RESULT_KEY_POSTS: ["demo-post-1", "demo-post-2"], RESULT_KEY_PROFILES: ["demo-profile-1"]}

    if params.table.count().execute() == 0:
        return {RESULT_KEY_POSTS: [], RESULT_KEY_PROFILES: []}

    # 1. Prepare dependencies (partial, will update with context later)
    resources = params.resources
    if params.run_id and resources.run_id is None:
        # Create new resources with run_id
        resources = dataclasses.replace(resources, run_id=params.run_id)

    # 2. Build context and calculate signature
    # We need to build context first to get XML for signature
    writer_context, signature = build_context_and_signature(
        WriterContextParams(
            table=params.table,
            resources=resources,
            cache=params.cache,
            config=params.config,
            window_label=f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
            adapter_content_summary=params.adapter_content_summary,
            adapter_generation_instructions=params.adapter_generation_instructions,
        ),
        resources.prompts_dir,
    )

    # 3. Check L3 cache
    cached_result = check_writer_cache(
        params.cache,
        signature,
        f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
        resources.usage,
    )
    if cached_result:
        # Validate cached posts still exist on disk (they may be missing if output dir is fresh)
        cached_posts = cached_result.get(RESULT_KEY_POSTS, [])
        if cached_posts:
            # Check if at least one post file exists
            posts_exist = any(
                list(resources.output.posts_dir.glob(f"*{slug}*.md"))
                for slug in cached_posts[:1]  # Check first post only for speed
            )
            if not posts_exist:
                logger.warning(
                    "⚠️ Cached posts not found on disk, regenerating for window %s",
                    f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
                )
                # Invalidate this cache entry
                params.cache.writer.delete(signature)
            else:
                # Posts exist, call finalize_window to mark completion and return
                resources.output.finalize_window(
                    window_label=f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
                    profiles_updated=cached_result.get(RESULT_KEY_PROFILES, []),
                    metadata=None,
                )
                return cached_result
        else:
            # No posts in cache, just return the empty result
            return cached_result

    logger.info("Using Pydantic AI backend for writer")

    # 4. Create Deps with the generated context
    deps = prepare_writer_dependencies(
        WriterDepsParams(
            window_start=params.window_start,
            window_end=params.window_end,
            resources=resources,
            model_name=params.config.models.writer,
            table=params.table,
            config=params.config,
            conversation_xml=writer_context.conversation_xml,
            active_authors=writer_context.active_authors,
            adapter_content_summary=params.adapter_content_summary,
            adapter_generation_instructions=params.adapter_generation_instructions,
        )
    )

    # 5. Render prompt and execute agent
    # NOTE: _render_writer_prompt uses writer_context, which we stripped RAG/Profiles from.
    # The Jinja template must be robust to missing/empty rag_context/profiles_context
    # OR we need to trust the dynamic system prompts to fill them in.
    # The current Jinja template (viewed earlier) has placeholders:
    # {% if profiles_context %}{{ profiles_context }}{% endif %}
    # If they are empty strings, they won't render in the user prompt, which is what we want,
    # because they will be injected by system prompts.

    prompt = _render_writer_prompt(writer_context, deps.resources.prompts_dir)

    saved_posts, saved_profiles = await _execute_writer_with_error_handling(prompt, params.config, deps)

    # 6. Finalize results (output, RAG indexing, caching)
    return _finalize_writer_results(
        WriterFinalizationParams(
            saved_posts=saved_posts,
            saved_profiles=saved_profiles,
            resources=resources,
            deps=deps,
            cache=params.cache,
            signature=signature,
        )
    )


def load_format_instructions(site_root: Path | None, *, registry: OutputSinkRegistry | None = None) -> str:
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
        .aggregate(count=table.author_uuid.count())
        .order_by(ibis.desc("count"))
        .limit(limit)
    )
    if author_counts.count().execute() == 0:
        return []
    return author_counts.author_uuid.cast("string").execute().tolist()
