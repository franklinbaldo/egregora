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
from egregora.agents.shared.rag import VectorStore
from egregora.agents.shared.rag.indexing import index_documents_for_rag
from egregora.agents.writer.agent import WriterAgentContext, write_posts_with_pydantic_agent
from egregora.agents.writer.context_builder import _load_profiles_context, build_rag_context_for_prompt
from egregora.agents.writer.formatting import _build_conversation_markdown, _load_journal_memory
from egregora.config import get_model_for_task
from egregora.config.settings import EgregoraConfig, create_default_config
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlContext
from egregora.output_adapters import create_output_format, output_registry
from egregora.output_adapters.mkdocs import MkDocsAdapter
from egregora.prompt_templates import WriterPromptTemplate

if TYPE_CHECKING:
    from google import genai
    from ibis.expr.types import Table

    from egregora.output_adapters.base import OutputAdapter


logger = logging.getLogger(__name__)


@dataclass
class WriterConfig:
    """Configuration for the writer functions.

    All embeddings use fixed 768-dimension output.
    """

    output_dir: Path = Path("output/posts")
    profiles_dir: Path = Path("output/profiles")
    rag_dir: Path = Path("output/rag")
    site_root: Path | None = None  # For custom prompt overrides in {site_root}/.egregora/prompts/
    egregora_config: EgregoraConfig | None = None
    cli_model: str | None = None
    enable_rag: bool = True
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None


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
        table: Table with 'author' column
        limit: Max number of authors (default 20)

    Returns:
        List of author UUIDs (most active first)

    """
    author_counts = (
        table.filter(~table.author.isin(["system", "egregora"]))
        .filter(table.author.notnull())
        .filter(table.author != "")
        .group_by("author")
        .aggregate(count=ibis._.count())
        .order_by(ibis.desc("count"))
        .limit(limit)
    )
    if author_counts.count().execute() == 0:
        return []
    return author_counts.author.execute().tolist()






def _build_writer_prompt(
    table_with_str_uuids, annotations_store, config, client, embedding_model,
    start_time, end_time, output_format, egregora_config, runtime_context
):
    """Builds the prompt for the writer agent."""
    messages_table = table_with_str_uuids.to_pyarrow()
    conversation_md = _build_conversation_markdown(messages_table, annotations_store)
    rag_context = ""
    if config.enable_rag:
        rag_context = build_rag_context_for_prompt(
            conversation_md, config.rag_dir, client,
            embedding_model=embedding_model,
            retrieval_mode=config.retrieval_mode,
            retrieval_nprobe=config.retrieval_nprobe,
            retrieval_overfetch=config.retrieval_overfetch,
            use_pydantic_helpers=True,
        )
    profiles_context = _load_profiles_context(table_with_str_uuids, config.profiles_dir)
    journal_memory = _load_journal_memory(config.rag_dir)
    active_authors = get_active_authors(table_with_str_uuids)

    date_range = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"
    format_instructions = output_format.get_format_instructions()
    custom_instructions = egregora_config.writer.custom_instructions or ""

    template = WriterPromptTemplate(
        date=date_range,
        markdown_table=conversation_md,
        active_authors=", ".join(active_authors),
        custom_instructions=custom_instructions,
        format_instructions=format_instructions,
        profiles_context=profiles_context,
        rag_context=rag_context,
        journal_memory=journal_memory,
        enable_memes=False,
        prompts_dir=runtime_context.prompts_dir,
    )
    return template.render()

def write_posts_for_window(
    table: Table, start_time: datetime, end_time: datetime,
    client: genai.Client, config: WriterConfig | None = None
) -> dict[str, list[str]]:
    """Orchestrates the post writing process for a given window."""
    if config is None:
        config = WriterConfig()
    if table.count().execute() == 0:
        return {"posts": [], "profiles": []}

    embedding_model = get_model_for_task("embedding", config.egregora_config, config.cli_model)
    annotations_store = AnnotationStore(config.rag_dir / "annotations.duckdb")

    table_with_str_uuids = table.mutate(
        event_id=table.event_id.cast(str),
        author_uuid=table.author_uuid.cast(str),
        thread_id=table.thread_id.cast(str),
        created_by_run=table.created_by_run.cast(str),
    )

    site_root = config.site_root
    if config.egregora_config is None:
        egregora_config = create_default_config(site_root) if site_root else create_default_config(Path.cwd())
    else:
        egregora_config = config.egregora_config.model_copy(deep=True)

    if config.cli_model:
        egregora_config.models.writer = config.cli_model
        egregora_config.models.embedding = config.cli_model

    storage_root = site_root if site_root else config.output_dir.parent
    rag_store = VectorStore(config.rag_dir / "chunks.parquet")
    prompts_dir = (storage_root / ".egregora" / "prompts" if (storage_root / ".egregora" / "prompts").is_dir() else None)

    output_format, runtime_output_format, url_convention = _create_runtime_output_handler(
        egregora_config.output.format, storage_root, UrlContext(base_url="", site_prefix="", base_path=storage_root)
    )

    runtime_context = WriterAgentContext(
        start_time=start_time, end_time=end_time,
        url_convention=url_convention, url_context=UrlContext(base_url="", site_prefix="", base_path=storage_root),
        output_format=runtime_output_format, rag_store=rag_store,
        annotations_store=annotations_store, client=client, prompts_dir=prompts_dir
    )

    prompt = _build_writer_prompt(
        table_with_str_uuids, annotations_store, config, client, embedding_model,
        start_time, end_time, output_format, egregora_config, runtime_context
    )

    try:
        saved_posts, saved_profiles = write_posts_with_pydantic_agent(
            prompt=prompt, config=egregora_config, context=runtime_context
        )
    except PromptTooLargeError:
        raise
    except Exception as exc:
        date_range = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"
        logger.exception("Writer agent failed for %s — aborting window", date_range)
        msg = f"Writer agent failed for {date_range}"
        raise RuntimeError(msg) from exc

    date_range = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"
    output_format.finalize_window(
        window_label=date_range, posts_created=saved_posts,
        profiles_updated=saved_profiles, metadata=None
    )

    if config.enable_rag and (saved_posts or saved_profiles):
        try:
            from egregora.agents.shared.rag.indexing import index_documents_for_rag
            indexed_count = index_documents_for_rag(
                output_format, config.rag_dir, embedding_model=embedding_model
            )
            if indexed_count > 0:
                logger.info("Indexed %d new/changed documents in RAG after writing", indexed_count)
        except Exception as e:
            logger.warning("Failed to update RAG index after writing: %s", e)

    return {"posts": saved_posts, "profiles": saved_profiles}
