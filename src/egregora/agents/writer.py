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

from egregora.agents.exceptions import AgentError
from egregora.agents.types import (
    PromptTooLargeError,
    WriterDeps,
    WriterResources,
)
from egregora.agents.writer_context import (
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
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter
from egregora.output_adapters.mkdocs.site_generator import SiteGenerator
from egregora.resources.prompts import render_prompt
from egregora.utils.cache import PipelineCache
from egregora.utils.retry import RETRY_IF, RETRY_STOP, RETRY_WAIT

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.config.settings import EgregoraConfig
    from egregora.data_primitives.document import OutputSink

logger = logging.getLogger(__name__)

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


def _save_journal_to_file(params: JournalEntryParams) -> str | None:
    """Save journal entry to markdown file.

    Raises:
        AgentError: If the journal template cannot be loaded, rendered, or written

    """
    intercalated_log = params.intercalated_log
    if not intercalated_log:
        return None

    templates_dir = Path(__file__).resolve().parents[1] / TEMPLATES_DIR_NAME
    now_utc = datetime.now(tz=UTC)
    window_start_iso = params.window_start.astimezone(UTC).isoformat()
    window_end_iso = params.window_end.astimezone(UTC).isoformat()
    journal_slug = now_utc.strftime("%Y-%m-%d-%H-%M-%S")

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
    except (TemplateNotFound, TemplateError) as exc:
        msg = f"Journal template error for window {params.window_label}: {exc}"
        logger.exception(msg)
        raise AgentError(msg) from exc
    except (OSError, PermissionError) as exc:
        msg = f"File system error during journal creation for window {params.window_label}: {exc}"
        logger.exception(msg)
        raise AgentError(msg) from exc


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
    agent = setup_writer_agent(model, prompt, config=config)

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

        msg = f"Writer agent failed for {deps.window_label}"
        logger.exception(msg)
        raise RuntimeError(msg) from exc


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
    _regenerate_site_indices(params.resources.output)

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
    smoke_test: bool = False


async def write_posts_for_window(params: WindowProcessingParams) -> dict[str, list[str]]:
    """Let LLM analyze window's messages, write 0-N posts, and update author profiles.

    This acts as the public entry point, orchestrating the setup and execution
    of the writer agent.
    """
    if params.smoke_test:
        logger.info("Smoke test mode: skipping writer agent.")
        return {RESULT_KEY_POSTS: [], RESULT_KEY_PROFILES: []}
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
            posts_exist = True
            if hasattr(resources.output, "posts_dir"):
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
                _regenerate_site_indices(resources.output)
                return cached_result
        else:
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

    if getattr(params.config.pipeline, "economic_mode", False):
        logger.info("💰 Economic Mode enabled: Using simple generation (no tools)")
        saved_posts, saved_profiles = await _execute_economic_writer(prompt, params.config, deps)
    else:
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


def _regenerate_site_indices(adapter: OutputSink) -> None:
    """Helper to regenerate all site indices using SiteGenerator."""
    if not isinstance(adapter, MkDocsAdapter):
        logger.debug("Output format is not MkDocs, skipping site generation.")
        return

    if not adapter.site_root:
        logger.warning("Site root is not set, skipping site generation.")
        return

    site_generator = SiteGenerator(
        site_root=adapter.site_root,
        docs_dir=adapter.docs_dir,
        posts_dir=adapter.posts_dir,
        profiles_dir=adapter.profiles_dir,
        media_dir=adapter.media_dir,
        journal_dir=adapter.journal_dir,
        url_convention=adapter.url_convention,
        url_context=adapter.url_context,
    )
    site_generator.regenerate_main_index()
    site_generator.regenerate_profiles_index()
    site_generator.regenerate_media_index()
    site_generator.regenerate_tags_page()
    logger.info("Successfully regenerated site indices.")


async def _execute_economic_writer(
    prompt: str,
    config: EgregoraConfig,
    deps: WriterDeps,
) -> tuple[list[str], list[str]]:
    """Execute writer in economic mode (one-shot, no tools, no streaming)."""
    import google.generativeai as genai  # Lazy import at runtime

    # 1. Create simple model for generation
    model_name = config.models.writer
    # Handle pydantic-ai prefix
    if model_name.startswith("google-gla:"):
        model_name = model_name.replace("google-gla:", "models/")

    # We use genai directly for simple generation to bypass pydantic-ai overhead/tools
    # Or we can use pydantic-ai agent without tools.
    # Let's use pydantic-ai agent without tools for consistency in dependency injection if needed,
    # BUT the user asked for "content generation instead of streaming" and "avoid tool usage".

    # Simple approach: Use genai.Client directly if available in deps, or creating one.
    # deps.resources.client should be a genai.Client
    client = deps.resources.client
    if not client:
        # Fallback creation if not in deps
        client = genai.Client()

    # We need to render system instructions (including RAG etc)
    # The current prompt variable contains the USER prompt (conversation XML).
    # We need the system instructions.

    # In full agent mode, system prompts are dynamic.
    # Here we should probably construct a simple system instruction or use the configured override.
    system_instruction = config.writer.economic_system_instruction
    if not system_instruction:
        system_instruction = (
            "You are an expert blog post writer. "
            "Analyze the provided conversation log and write a blog post summarizing it. "
            "Return ONLY the markdown content of the post. "
            "Do not use any tools."
        )

    # Add custom instructions if available (append to base/override instruction)
    if deps.config and deps.config.writer.custom_instructions:
        system_instruction += f"\n\n{deps.config.writer.custom_instructions}"

    temperature = config.writer.economic_temperature

    logger.info("Generating content (Economic Mode, temp=%.1f)...", temperature)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt],
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
            ),
        )

        content = response.text or ""

        # Extract title from content if possible
        title = f"Summary: {deps.window_start.strftime('%Y-%m-%d')}"
        lines = content.strip().splitlines()
        if lines and lines[0].startswith("# "):
            potential_title = lines[0][2:].strip()
            if potential_title:
                title = potential_title

        # Save content as a post
        # We need to manually create a document since we aren't using the tool
        # Generate a slug/filename
        slug = f"{deps.window_start.strftime('%Y-%m-%d')}-summary"

        doc = Document(
            content=content,
            type=DocumentType.POST,
            metadata={
                "slug": slug,
                "date": deps.window_start.strftime("%Y-%m-%d"),
                "title": title,
            },
            source_window=deps.window_label,
        )

        deps.resources.output.persist(doc)
        logger.info("Saved economic post: %s", doc.document_id)

        return [doc.document_id], []

    except Exception as e:
        logger.exception("Economic writer failed")
        msg = f"Economic writer failed: {e}"
        raise RuntimeError(msg) from e


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
