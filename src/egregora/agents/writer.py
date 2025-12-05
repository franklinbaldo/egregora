"""Pydantic-AI powered writer agent.

This module implements the writer workflow using Pydantic-AI.
It acts as the Composition Root for the agent, assembling core tools and
capabilities before executing the conversation through a ``pydantic_ai.Agent``.
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
from pydantic_ai import Agent, RunContext, UsageLimits
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

from egregora.agents.banner.agent import is_banner_generation_available
from egregora.agents.capabilities import (
    AgentCapability,
    BackgroundBannerCapability,
    BannerCapability,
    RagCapability,
)
from egregora.agents.formatting import (
    build_conversation_xml,
    load_journal_memory,
)
from egregora.agents.model_limits import (
    PromptTooLargeError,
    get_model_context_limit,
    validate_prompt_fits,
)
from egregora.agents.types import (
    AnnotationResult,
    PostMetadata,
    ReadProfileResult,
    WritePostResult,
    WriteProfileResult,
    WriterAgentReturn,
    WriterDeps,
    WriterResources,
)
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
from egregora.knowledge.profiles import get_active_authors, read_profile
from egregora.output_adapters import OutputAdapterRegistry, create_default_output_registry
from egregora.rag import index_documents, reset_backend
from egregora.resources.prompts import PromptManager, render_prompt
from egregora.transformations.windowing import generate_window_signature
from egregora.utils.batch import RETRY_IF, RETRY_STOP, RETRY_WAIT
from egregora.utils.cache import CacheTier, PipelineCache
from egregora.utils.metrics import UsageTracker
from egregora.utils.quota import QuotaExceededError

if TYPE_CHECKING:
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
        # NOTE: reset_backend() not strictly needed in sync mode but included as defensive
        # programming to clear any loop-bound clients from previous async operations
        reset_backend()

        request = RAGQueryRequest(text=query_text, top_k=top_k)
        response = search(request)

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
        logger.exception("Malformed RAG response, continuing without context: %s", exc)
        return ""


def _load_profiles_context(active_authors: list[str], profiles_dir: Path) -> str:
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
    conversation_xml = build_conversation_xml(messages_table, resources.annotations_store)

    # CACHE INVALIDATION STRATEGY:
    # RAG and Profiles context building moved to dynamic system prompts for lazy evaluation.
    # This creates a cache trade-off:
    #
    # Trade-off: Cache signature includes conversation XML but NOT RAG/Profile results
    # - Pro: Avoids expensive RAG/Profile computation for signature calculation
    # - Con: Cache hit may use stale data if RAG index changes but conversation doesn't
    #
    # Mitigation strategies (not currently implemented):
    # 1. Include RAG index version/timestamp in signature
    # 2. Add cache TTL for RAG-enabled runs
    # 3. Manual cache invalidation when RAG index is updated
    #
    # Current behavior: Cache is conversation-scoped only. If RAG data changes
    # but conversation is identical, cached results will be used.
    # This is acceptable for most use cases where conversation changes drive cache invalidation.

    rag_context = ""  # Dynamically injected via @agent.system_prompt
    profiles_context = ""  # Dynamically injected via @agent.system_prompt

    journal_memory = load_journal_memory(resources.output)
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
        logger.exception("Journal template not found: %s", exc)
        return None
    except (OSError, PermissionError) as exc:
        logger.exception("Cannot access template directory: %s", exc)
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
        logger.exception("Journal template rendering failed: %s", exc)
        return None
    except (TypeError, AttributeError) as exc:
        logger.exception("Invalid template data for journal: %s", exc)
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
    except (OSError, PermissionError) as exc:
        logger.exception("Failed to write journal to disk: %s", exc)
        return None
    except ValueError as exc:
        logger.exception("Invalid journal document: %s", exc)
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

        if data.get("status") in ("success", "scheduled") and "path" in data:
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
        quota=ctx.quota_tracker,
        usage=ctx.usage_tracker,
        output_registry=getattr(ctx, "output_registry", None),
        run_id=ctx.run_id,
    )

    return _prepare_writer_dependencies(window_start, window_end, resources, ctx.config.models.writer)


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

    active_capabilities: list[AgentCapability] = []
    if config.rag.enabled:
        active_capabilities.append(RagCapability())

    if is_banner_generation_available():
        if context.resources.task_store and context.resources.run_id:
            active_capabilities.append(BackgroundBannerCapability(context.resources.run_id))
        else:
            active_capabilities.append(BannerCapability())

    if active_capabilities:
        caps_list = ", ".join(capability.name for capability in active_capabilities)
        logger.info("Writer capabilities enabled: %s", caps_list)

    # Define a simple provider to wrap the SDK client
    class SimpleProvider:
        def __init__(self, client) -> None:
            self._client = client
            self.model_profile = None

        @property
        def client(self):
            return self._client

        def name(self) -> str:
            return "google-gla"

        @property
        def base_url(self) -> str:
            return "https://generativelanguage.googleapis.com/v1beta/"

    from egregora.utils.model_fallback import create_fallback_model

    # Create model with automatic fallback
    configured_model = test_model if test_model is not None else config.models.writer
    model = create_fallback_model(configured_model, use_google_batch=False)

    # Validate prompt fits (using the initial prompt, dynamic parts are checked during run by usage limits or provider)
    _validate_prompt_fits(prompt, configured_model, config, context.window_label)

    # Create agent
    agent = Agent[WriterDeps, WriterAgentReturn](
        model=model,
        deps_type=WriterDeps,
        # Allow a few validation retries so transient schema hiccups don't abort the run
        retries=3,
        system_prompt=prompt, # Static instructions
    )
    register_writer_tools(agent, capabilities=active_capabilities)

    # Dynamic System Prompts
    @agent.system_prompt
    def inject_rag_context(ctx: RunContext[WriterDeps]) -> str:
        # Only run RAG if enabled
        if ctx.deps.resources.retrieval_config.enabled:
            # We use the conversation XML as the query source, which should be in deps
            table_markdown = ctx.deps.conversation_xml
            return build_rag_context_for_prompt(
                table_markdown,
                top_k=ctx.deps.resources.retrieval_config.top_k,
                cache=None, # Cache not available inside system prompt easily, or we could pass it if we attached it to Deps
            )
        return ""

    @agent.system_prompt
    def inject_profiles_context(ctx: RunContext[WriterDeps]) -> str:
        # Inject profiles
        return _load_profiles_context(ctx.deps.active_authors, ctx.deps.resources.profiles_dir)

    if context.resources.quota:
        context.resources.quota.reserve(1)

        # Should be unreachable due to reraise=True
        msg = "Agent failed after retries"
        raise RuntimeError(msg)

    result = None
    # Use tenacity for retries
    for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
        with attempt:
            # DIRECT SYNC CALL
            result = agent.run_sync(
                "Analyze the conversation context provided and write posts/profiles as needed.",
                deps=context,
                usage_limits=usage_limits
            )

    if not result:
         # Should be unreachable due to reraise=True
        raise RuntimeError("Agent failed after retries")

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
            index_documents(docs)
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
    finally:
        # Reset backend to clear loop-bound clients (httpx) as defensive programming
        # NOTE: Not strictly needed in sync mode but prevents potential issues
        # if async operations are added in the future or called from async contexts
        reset_backend()


def _prepare_writer_dependencies(
    window_start: datetime,
    window_end: datetime,
    resources: WriterResources,
    model_name: str,
    # Added for dynamic context
    table: Table | None = None,
    config: EgregoraConfig | None = None,
    conversation_xml: str = "",
    active_authors: list[str] | None = None,
    adapter_content_summary: str = "",
    adapter_generation_instructions: str = "",
) -> WriterDeps:
    """Create WriterDeps from window parameters and resources."""
    window_label = f"{window_start:%Y-%m-%d %H:%M} to {window_end:%H:%M}"

    return WriterDeps(
        resources=resources,
        window_start=window_start,
        window_end=window_end,
        window_label=window_label,
        model_name=model_name,
        table=table,
        config=config,
        conversation_xml=conversation_xml,
        active_authors=active_authors or [],
        adapter_content_summary=adapter_content_summary,
        adapter_generation_instructions=adapter_generation_instructions,
    )


def _build_context_and_signature(
    table: Table,
    resources: WriterResources,
    cache: PipelineCache,
    config: EgregoraConfig,
    window_label: str,
    adapter_content_summary: str,
    adapter_generation_instructions: str,
    prompts_dir: Path | None,
) -> tuple[WriterContext, str]:
    """Build writer context and calculate cache signature.

    Returns:
        Tuple of (writer_context, cache_signature)

    """
    table_with_str_uuids = _cast_uuid_columns_to_str(table)

    # Generate context for both prompt and signature
    # This now just generates the base context (XML, Journal) which is cheap(er)
    writer_context = _build_writer_context(
        table_with_str_uuids,
        resources,
        cache,
        config,
        window_label,
        adapter_content_summary,
        adapter_generation_instructions,
    )

    # Get template content for signature calculation
    template_content = PromptManager.get_template_content("writer.jinja", custom_prompts_dir=prompts_dir)

    # Calculate signature using data (XML) + logic (template) + engine
    signature = generate_window_signature(
        table_with_str_uuids, config, template_content, xml_content=writer_context.conversation_xml
    )

    return writer_context, signature


def _execute_writer_with_error_handling(
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
        return write_posts_with_pydantic_agent(
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


def _finalize_writer_results(
    saved_posts: list[str],
    saved_profiles: list[str],
    resources: WriterResources,
    deps: WriterDeps,
    cache: PipelineCache,
    signature: str,
) -> dict[str, list[str]]:
    """Finalize window results: output, RAG indexing, and caching.

    Returns:
        Result payload dict with 'posts' and 'profiles' keys

    """
    # Finalize output adapter
    resources.output.finalize_window(
        window_label=deps.window_label,
        posts_created=saved_posts,
        profiles_updated=saved_profiles,
        metadata=None,
    )

    # Index newly created content in RAG
    _index_new_content_in_rag(resources, saved_posts, saved_profiles)

    # Update L3 cache
    result_payload = {RESULT_KEY_POSTS: saved_posts, RESULT_KEY_PROFILES: saved_profiles}
    cache.writer.set(signature, result_payload)

    return result_payload


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
    run_id: str | None = None,
) -> dict[str, list[str]]:
    """Let LLM analyze window's messages, write 0-N posts, and update author profiles.

    This acts as the public entry point, orchestrating the setup and execution
    of the writer agent.
    """
    if table.count().execute() == 0:
        return {RESULT_KEY_POSTS: [], RESULT_KEY_PROFILES: []}

    # 1. Prepare dependencies (partial, will update with context later)
    if run_id and resources.run_id is None:
        # Create new resources with run_id
        import dataclasses

        resources = dataclasses.replace(resources, run_id=run_id)

    # 2. Build context and calculate signature
    # We need to build context first to get XML for signature
    writer_context, signature = _build_context_and_signature(
        table,
        resources,
        cache,
        config,
        f"{window_start:%Y-%m-%d %H:%M} to {window_end:%H:%M}",
        adapter_content_summary,
        adapter_generation_instructions,
        resources.prompts_dir,
    )

    # 3. Check L3 cache
    cached_result = _check_writer_cache(cache, signature, f"{window_start:%Y-%m-%d %H:%M} to {window_end:%H:%M}", resources.usage)
    if cached_result:
        return cached_result

    logger.info("Using Pydantic AI backend for writer")

    # 4. Create Deps with the generated context
    deps = _prepare_writer_dependencies(
        window_start,
        window_end,
        resources,
        config.models.writer,
        table=table,
        config=config,
        conversation_xml=writer_context.conversation_xml,
        active_authors=writer_context.active_authors,
        adapter_content_summary=adapter_content_summary,
        adapter_generation_instructions=adapter_generation_instructions
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
    saved_posts, saved_profiles = _execute_writer_with_error_handling(prompt, config, deps)

    # 6. Finalize results (output, RAG indexing, caching)
    return _finalize_writer_results(saved_posts, saved_profiles, resources, deps, cache, signature)


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
        .aggregate(count=table.author_uuid.count())
        .order_by(ibis.desc("count"))
        .limit(limit)
    )
    if author_counts.count().execute() == 0:
        return []
    return author_counts.author_uuid.cast("string").execute().tolist()
