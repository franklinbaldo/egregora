"""Simple writer: LLM with write_post tool for editorial control.

The LLM decides what's worth writing, how many posts to create, and all metadata.
Uses function calling (write_post tool) to generate 0-N posts per window.

Documentation:
- Multi-Post Generation: docs/features/multi-post.md
- Architecture (Writer): docs/guides/architecture.md#5-writer-writerpy
- Core Concepts (Editorial Control):
  docs/getting-started/concepts.md#editorial-control-llm-decision-making
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import ibis

from egregora.agents.model_limits import PromptTooLargeError
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.shared.author_profiles import get_active_authors
from egregora.agents.shared.rag import VectorStore, index_document
from egregora.agents.writer.agent import WriterAgentContext, write_posts_with_pydantic_agent
from egregora.agents.writer.context_builder import _load_profiles_context, build_rag_context_for_prompt
from egregora.agents.writer.formatting import _build_conversation_markdown_table, _load_journal_memory
from egregora.config.settings import EgregoraConfig, create_default_config
from egregora.data_primitives.protocols import UrlContext
from egregora.orchestration.context import PipelineContext
from egregora.output_adapters import create_output_format, output_registry
from egregora.output_adapters.mkdocs import MkDocsAdapter
from egregora.prompt_templates import render_prompt

if TYPE_CHECKING:
    from google import genai
    from ibis.expr.types import Table

    from egregora.output_adapters.base import OutputAdapter


logger = logging.getLogger(__name__)


MAX_CONVERSATION_TURNS = 10


def load_format_instructions(site_root: Path | None) -> str:
    """Load output format instructions for the writer agent.

    Detects the output format (MkDocs, Hugo, etc.) and returns format-specific
    instructions that teach the LLM about conventions like front-matter syntax,
    file naming, special features, etc.

    Args:
        site_root: Site root directory (for format detection)

    Returns:
        Markdown-formatted instructions explaining the output format

    """
    # Try to detect format from site structure
    if site_root:
        detected_format = output_registry.detect_format(site_root)
        if detected_format:
            logger.info("Detected output format: %s", detected_format.format_type)
            return detected_format.get_format_instructions()

    # Fall back to 'mkdocs' format from registry
    try:
        default_format = output_registry.get_format("mkdocs")
        logger.debug("Using default format: mkdocs")
        return default_format.get_format_instructions()
    except KeyError:
        # If mkdocs isn't registered, return empty string
        logger.warning("No output format detected and 'mkdocs' not registered")
        return ""


def get_top_authors(table: Table, limit: int = 20) -> list[str]:
    """Get top N active authors by message count.

    Args:
        table: Table with IR schema (uses 'author_uuid' column)
        limit: Max number of authors (default 20)

    Returns:
        List of author UUIDs (most active first)

    """
    # IR v1: use 'author_uuid' instead of 'author'
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


def _fetch_format_documents(output_format: OutputAdapter) -> tuple[list, int] | tuple[None, int]:
    """Return all documents known to the output adapter and their count.

    Returns:
        (list[Document], count) if documents exist, (None, 0) otherwise

    """
    format_documents = output_format.list_documents()

    # RAG works with Documents directly, not paths
    if isinstance(format_documents, list):
        doc_count = len(format_documents)
        if doc_count == 0:
            logger.debug("No documents found by output format")
            return None, 0
        logger.debug("OutputAdapter reported %d documents", doc_count)
        return format_documents, doc_count
    # Legacy: convert Table to list of dicts
    doc_count = format_documents.count().execute()
    if doc_count == 0:
        logger.debug("No documents found by output format")
        return None, 0
    logger.debug("OutputAdapter reported %d documents", doc_count)
    return format_documents.execute().to_dict("records"), doc_count


# Removed legacy path-based helper functions:
# - _detect_changed_documents() - used Ibis joins to find changed files
# - _index_documents() - loaded documents from paths
# Now using Document objects directly from OutputAdapter


def index_documents_for_rag(
    output_format: OutputAdapter, rag_store: VectorStore, *, embedding_model: str
) -> int:
    """Index documents directly from OutputAdapter into RAG vector store.

    MODERN: Works with Document objects directly (no filesystem paths needed).
    OutputAdapter provides Documents with content already loaded.

    This should be called once at pipeline initialization before window processing.

    Args:
        output_format: OutputAdapter instance (initialized with site_root)
        rag_store: VectorStore instance
        embedding_model: Model to use for embeddings

    Returns:
        Number of documents indexed

    """
    try:
        format_documents, doc_count = _fetch_format_documents(output_format)
        if format_documents is None:
            logger.debug("No documents found to index")
            return 0

        # Get already-indexed document IDs for deduplication
        indexed_ids = set()
        try:
            indexed_table = rag_store.get_indexed_sources_table()
            if indexed_table.count().execute() > 0:
                # Assuming source_path contains document_id for Document-based indexing
                indexed_ids = set(indexed_table.source_path.execute().tolist())
        except Exception as e:
            logger.debug("No existing index found (first run): %s", e)

        # Index only new documents (not already indexed)
        indexed_count = 0
        for doc in format_documents:
            if doc.document_id in indexed_ids:
                logger.debug("Skipping already-indexed document: %s", doc.document_id)
                continue

            try:
                index_document(
                    doc,
                    rag_store,
                    embedding_model=embedding_model,
                    source_path=doc.document_id,  # Use document_id as identifier
                    source_mtime_ns=int(doc.created_at.timestamp() * 1_000_000_000),
                )
                indexed_count += 1
                logger.debug("Indexed document: %s", doc.document_id)
            except Exception as e:  # noqa: BLE001 - logging and continuing is intentional
                logger.warning("Failed to index document %s: %s", doc.document_id, e)
                continue

        if indexed_count > 0:
            logger.info("Indexed %d new documents in RAG (total: %d)", indexed_count, doc_count)
        else:
            logger.debug("All %d documents already indexed", doc_count)

        return indexed_count

    except PromptTooLargeError:
        raise
    except Exception:
        # RAG indexing is non-critical - log error but don't fail pipeline
        logger.exception("Failed to index documents in RAG")
        return 0


def _cast_uuid_columns_to_str(table: Table) -> Table:
    """Ensure UUID-like columns are serialised to strings for downstream consumers."""
    return table.mutate(
        event_id=table.event_id.cast(str),
        author_uuid=table.author_uuid.cast(str),
        thread_id=table.thread_id.cast(str),
        created_by_run=table.created_by_run.cast(str),
    )


def _build_writer_agent_context(
    ctx: PipelineContext,
    window_start: datetime,
    window_end: datetime,
) -> WriterAgentContext:
    """Construct WriterAgentContext from PipelineContext for a specific window.

    Args:
        ctx: Unified pipeline context with configuration and resources
        window_start: Start timestamp of the window
        window_end: End timestamp of the window

    Returns:
        WriterAgentContext configured for this window
    """
    storage_root = ctx.site_root if ctx.site_root else ctx.output_dir
    format_type = ctx.config.output.format

    # Determine prompts directory
    prompts_dir = (
        storage_root / ".egregora" / "prompts" if (storage_root / ".egregora" / "prompts").is_dir() else None
    )

    # Use existing output_format from context, or create runtime format if needed
    if format_type == "mkdocs" and ctx.output_format:
        runtime_output_format = MkDocsAdapter()
        url_context = ctx.url_context or UrlContext(base_url="", site_prefix="", base_path=storage_root)
        runtime_output_format.initialize(site_root=storage_root, url_context=url_context)
        url_convention = runtime_output_format.url_convention
    elif ctx.output_format:
        runtime_output_format = ctx.output_format
        url_convention = runtime_output_format.url_convention
        url_context = ctx.url_context or UrlContext(base_url="", site_prefix="", base_path=storage_root)
        logger.debug("Using url_convention from %s adapter", format_type)
    else:
        # Fallback: create output format
        output_format = create_output_format(storage_root, format_type=format_type)
        runtime_output_format = output_format
        url_convention = output_format.url_convention
        url_context = UrlContext(base_url="", site_prefix="", base_path=storage_root)

    return WriterAgentContext(
        start_time=window_start,
        end_time=window_end,
        url_convention=url_convention,
        url_context=url_context,
        output_format=runtime_output_format,
        rag_store=ctx.rag_store,
        annotations_store=ctx.annotations_store,
        client=ctx.client,
        prompts_dir=prompts_dir,
    )


@dataclass
class WriterPromptContext:
    """Values used to populate the writer prompt template."""

    conversation_md: str
    rag_context: str
    profiles_context: str
    journal_memory: str
    active_authors: list[str]


def _build_writer_prompt_context(
    table_with_str_uuids: Table,
    ctx: PipelineContext,
) -> WriterPromptContext:
    """Collect contextual inputs used when rendering the writer prompt.

    Args:
        table_with_str_uuids: Message table with UUIDs cast to strings
        ctx: Pipeline context with configuration and resources

    Returns:
        WriterPromptContext with all prompt components
    """
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
            use_pydantic_helpers=True,
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


def _render_writer_prompt(
    prompt_context: WriterPromptContext,
    ctx: PipelineContext,
    agent_context: WriterAgentContext,
    *,
    date_range: str,
) -> str:
    """Render the final writer prompt text.

    Args:
        prompt_context: Collected prompt components (conversation, RAG, profiles, etc.)
        ctx: Pipeline context with configuration
        agent_context: Writer agent context with runtime resources
        date_range: Human-readable date range for the window

    Returns:
        Rendered prompt text
    """
    format_instructions = (
        ctx.output_format.get_format_instructions() if ctx.output_format else ""
    )
    custom_instructions = ctx.config.writer.custom_instructions or ""

    return render_prompt(
        "system/writer.jinja",
        prompts_dir=agent_context.prompts_dir,
        date=date_range,
        markdown_table=prompt_context.conversation_md,
        active_authors=", ".join(prompt_context.active_authors),
        custom_instructions=custom_instructions,
        format_instructions=format_instructions,
        profiles_context=prompt_context.profiles_context,
        rag_context=prompt_context.rag_context,
        journal_memory=prompt_context.journal_memory,
        enable_memes=False,
    )


def _write_posts_for_window_pydantic(
    table: Table,
    window_start: datetime,
    window_end: datetime,
    ctx: PipelineContext,
) -> dict[str, list[str]]:
    """Pydantic AI backend: Let LLM analyze window's messages using Pydantic AI.

    This is the new implementation using Pydantic AI for type safety and observability.
    Automatically traces to Logfire if LOGFIRE_TOKEN is set.

    Args:
        table: Table with messages for the period (already enriched)
        window_start: Start timestamp of the window
        window_end: End timestamp of the window
        ctx: Pipeline context with configuration and resources

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths

    """
    if table.count().execute() == 0:
        return {"posts": [], "profiles": []}

    # Build window-specific agent context from pipeline context
    agent_context = _build_writer_agent_context(ctx, window_start, window_end)

    # Build prompt context from table and pipeline context
    table_with_str_uuids = _cast_uuid_columns_to_str(table)
    prompt_context = _build_writer_prompt_context(table_with_str_uuids, ctx)

    # Render the prompt
    date_range = f"{window_start:%Y-%m-%d %H:%M} to {window_end:%H:%M}"
    prompt = _render_writer_prompt(prompt_context, ctx, agent_context, date_range=date_range)

    # Execute the writer agent
    try:
        saved_posts, saved_profiles = write_posts_with_pydantic_agent(
            prompt=prompt,
            config=ctx.config,
            context=agent_context,
        )
    except PromptTooLargeError:
        raise
    except Exception as exc:
        logger.exception("Writer agent failed for %s — aborting window", date_range)
        msg = f"Writer agent failed for {date_range}"
        raise RuntimeError(msg) from exc

    # Call format-specific finalization hook (e.g., update .authors.yml, regenerate indexes)
    if ctx.output_format:
        ctx.output_format.finalize_window(
            window_label=date_range,
            posts_created=saved_posts,
            profiles_updated=saved_profiles,
            metadata=None,  # Future: pass token counts, duration, etc.
        )

    # Index new/changed documents in RAG after writing
    # Uses native deduplication via Ibis joins - safe to call anytime
    if ctx.enable_rag and ctx.rag_store and ctx.output_format and (saved_posts or saved_profiles):
        try:
            indexed_count = index_documents_for_rag(
                ctx.output_format,
                ctx.rag_store,
                embedding_model=ctx.embedding_model,
            )
            if indexed_count > 0:
                logger.info("Indexed %d new/changed documents in RAG after writing", indexed_count)
        except Exception as e:
            # RAG indexing is non-critical - log error but don't fail
            logger.warning("Failed to update RAG index after writing: %s", e)

    return {"posts": saved_posts, "profiles": saved_profiles}


def write_posts_for_window(
    table: Table,
    window_start: datetime,
    window_end: datetime,
    ctx: PipelineContext,
) -> dict[str, list[str]]:
    """Let LLM analyze window's messages, write 0-N posts, and update author profiles.

    Uses Pydantic AI for type safety and Logfire observability.

    The LLM has full editorial control via tools:
    - write_post: Create blog posts with metadata
    - read_profile: Read existing author profiles
    - write_profile: Update author profiles

    RAG system provides context from previous posts for continuity.

    Args:
        table: Table with messages for the period (already enriched)
        window_start: Start timestamp of the window
        window_end: End timestamp of the window
        ctx: Pipeline context with configuration and resources

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths

    Environment Variables:
        LOGFIRE_TOKEN: Optional, enables Logfire observability

    Examples:
        >>> from egregora.orchestration.context import PipelineContext
        >>> start = datetime(2025, 1, 1, 0, 0)
        >>> end = datetime(2025, 1, 1, 23, 59)
        >>> result = write_posts_for_window(table, start, end, ctx)

    """
    logger.info("Using Pydantic AI backend for writer")
    return _write_posts_for_window_pydantic(
        table=table,
        window_start=window_start,
        window_end=window_end,
        ctx=ctx,
    )
