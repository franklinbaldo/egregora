"""Pydantic-AI powered writer agent.

This module implements the writer workflow using Pydantic-AI.
It acts as the Composition Root for the agent, assembling core tools and
capabilities before executing the conversation through a ``pydantic_ai.Agent``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import ibis.common.exceptions
from ibis.expr.types import Table
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.exceptions import TemplateError, TemplateNotFound
from pydantic_ai import Agent, RunContext
from ratelimit import limits, sleep_and_retry
from tenacity import Retrying

from egregora.agents.banner.agent import is_banner_generation_available
from egregora.agents.capabilities import (
    AgentCapability,
    BackgroundBannerCapability,
    BannerCapability,
    RagCapability,
)
from egregora.agents.model_limits import (
    PromptTooLargeError,
    get_model_context_limit,
    validate_prompt_fits,
)
from egregora.agents.types import PostMetadata, WriterAgentReturn, WriterDeps, WriterResources
from egregora.agents.writer_context import WriterContext, build_writer_context
from egregora.agents.writer_extraction import (
    JOURNAL_TYPE_TEXT,
    JournalEntry,
    extract_journal_content,
    extract_intercalated_log,
    extract_tool_results,
)
from egregora.agents.writer_tools import (
    AnnotationContext,
    AnnotationResult,
    ReadProfileResult,
    ToolContext,
    WritePostResult,
    WriteProfileResult,
    annotate_conversation_impl,
    read_profile_impl,
    write_post_impl,
    write_profile_impl,
)
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
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

logger = logging.getLogger(__name__)

# Constants
WRITER_TEMPLATE_NAME = "writer.jinja"
JOURNAL_TEMPLATE_NAME = "journal.md.jinja"
TEMPLATES_DIR_NAME = "templates"
RESULT_KEY_POSTS = "posts"
RESULT_KEY_PROFILES = "profiles"

# Type aliases
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
        tool_ctx = ToolContext(
            output_sink=ctx.deps.resources.output,
            window_label=ctx.deps.window_label,
        )
        meta_dict = metadata.model_dump(exclude_none=True)
        meta_dict["model"] = ctx.deps.model_name
        return write_post_impl(tool_ctx, meta_dict, content)

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str) -> ReadProfileResult:
        tool_ctx = ToolContext(
            output_sink=ctx.deps.resources.output,
            window_label=ctx.deps.window_label,
        )
        return read_profile_impl(tool_ctx, author_uuid)

    @agent.tool
    def write_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str, content: str) -> WriteProfileResult:
        tool_ctx = ToolContext(
            output_sink=ctx.deps.resources.output,
            window_label=ctx.deps.window_label,
        )
        return write_profile_impl(tool_ctx, author_uuid, content)

    @agent.tool
    def annotate_conversation_tool(
        ctx: RunContext[WriterDeps], parent_id: str, parent_type: str, commentary: str
    ) -> AnnotationResult:
        """Annotate a message or another annotation with commentary."""
        annot_ctx = AnnotationContext(annotations_store=ctx.deps.resources.annotations_store)
        return annotate_conversation_impl(annot_ctx, parent_id, parent_type, commentary)

    for capability in capabilities:
        logger.debug("Registering capability: %s", capability.name)
        capability.register(agent)


# ============================================================================
# Core Logic
# ============================================================================


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


def _prepare_deps(
    ctx: Any,  # PipelineContext
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


def _validate_prompt_fits_wrapper(
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

    from egregora.utils.model_fallback import create_fallback_model

    # Create model with automatic fallback
    configured_model = test_model if test_model is not None else config.models.writer
    model = create_fallback_model(configured_model, use_google_batch=False)

    # Validate prompt fits
    _validate_prompt_fits_wrapper(prompt, configured_model, config, context.window_label)

    # Create agent
    agent = Agent[WriterDeps, WriterAgentReturn](
        model=model,
        deps_type=WriterDeps,
        # Allow a few validation retries so transient schema hiccups don't abort the run
        retries=3,
        output_retries=3,
    )
    register_writer_tools(agent, capabilities=active_capabilities)

    reset_backend()
    try:
        if context.resources.quota:
            context.resources.quota.reserve(1)
        for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
            with attempt:
                result = agent.run_sync(prompt, deps=context)
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

    # Extract results using helper module
    saved_posts, saved_profiles = extract_tool_results(result.all_messages())
    intercalated_log = extract_intercalated_log(result.all_messages())

    if not intercalated_log:
        fallback_content = extract_journal_content(result.all_messages())
        if fallback_content:
            # Strip frontmatter if present
            if fallback_content.strip().startswith("---"):
                try:
                    _, _, body = fallback_content.strip().split("---", 2)
                    fallback_content = body.strip()
                except ValueError:
                    pass

            intercalated_log = [JournalEntry(JOURNAL_TYPE_TEXT, fallback_content, datetime.now(tz=UTC))]
        else:
            intercalated_log = [
                JournalEntry(
                    JOURNAL_TYPE_TEXT,
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
    """Check L3 cache for cached writer results."""
    if cache.should_refresh(CacheTier.WRITER):
        return None

    cached_result = cache.writer.get(signature)
    if cached_result:
        logger.info("⚡ [L3 Cache Hit] Skipping Writer LLM for window %s", window_label)
        if usage_tracker:
            pass  # Usage tracker doesn't track cache hits currently
    return cached_result


def _index_new_content_in_rag(
    resources: WriterResources,
    saved_posts: list[str],
) -> None:
    """Index newly created content in RAG system."""
    if not (resources.retrieval_config.enabled and saved_posts):
        return

    try:
        docs: list[Document] = []
        for post_id in saved_posts:
            if hasattr(resources.output, "documents"):
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
        logger.warning("RAG backend unavailable for indexing, skipping: %s", exc)
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid document data for RAG indexing, skipping: %s", exc)
    except (OSError, PermissionError) as exc:
        logger.warning("Cannot access RAG storage, skipping indexing: %s", exc)


def _prepare_writer_dependencies(
    window_start: datetime,
    window_end: datetime,
    resources: WriterResources,
    model_name: str,
) -> WriterDeps:
    """Create WriterDeps from window parameters and resources."""
    window_label = f"{window_start:%Y-%m-%d %H:%M} to {window_end:%H:%M}"

    return WriterDeps(
        resources=resources,
        window_start=window_start,
        window_end=window_end,
        window_label=window_label,
        model_name=model_name,
    )


def _execute_writer_with_error_handling(
    prompt: str,
    config: EgregoraConfig,
    deps: WriterDeps,
) -> tuple[list[str], list[str]]:
    """Execute writer agent with proper error handling."""
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
    """Finalize window results: output, RAG indexing, and caching."""
    # Finalize output adapter
    resources.output.finalize_window(
        window_label=deps.window_label,
        posts_created=saved_posts,
        profiles_updated=saved_profiles,
        metadata=None,
    )

    # Index newly created content in RAG
    _index_new_content_in_rag(resources, saved_posts)

    # Update L3 cache
    result_payload = {RESULT_KEY_POSTS: saved_posts, RESULT_KEY_PROFILES: saved_profiles}
    cache.writer.set(signature, result_payload)

    return result_payload


def write_posts_for_window(  # noqa: PLR0913
    table: Table,
    window_start: datetime,
    window_end: datetime,
    resources: WriterResources,
    config: EgregoraConfig,
    cache: PipelineCache,
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

    # 1. Prepare dependencies
    if run_id and resources.run_id is None:
        import dataclasses

        resources = dataclasses.replace(resources, run_id=run_id)

    deps = _prepare_writer_dependencies(window_start, window_end, resources, config.models.writer)

    # 2. Build context and calculate signature
    table_with_str_uuids = _cast_uuid_columns_to_str(table)

    writer_context = build_writer_context(
        table_with_str_uuids,
        resources,
        cache,
        config,
        deps.window_label,
        adapter_content_summary,
        adapter_generation_instructions,
    )

    template_content = PromptManager.get_template_content("writer.jinja", custom_prompts_dir=deps.resources.prompts_dir)
    signature = generate_window_signature(
        table_with_str_uuids, config, template_content, xml_content=writer_context.conversation_xml
    )

    # 3. Check L3 cache
    cached_result = _check_writer_cache(cache, signature, deps.window_label, deps.resources.usage)
    if cached_result:
        return cached_result

    logger.info("Using Pydantic AI backend for writer")

    # 4. Render prompt and execute agent
    prompt = _render_writer_prompt(writer_context, deps.resources.prompts_dir)
    saved_posts, saved_profiles = _execute_writer_with_error_handling(prompt, config, deps)

    # 5. Finalize results
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
