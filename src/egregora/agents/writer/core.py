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
from typing import TYPE_CHECKING, Any

import ibis
import yaml

from egregora.agents.model_limits import PromptTooLargeError
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.shared.profiler import get_active_authors
from egregora.agents.shared.rag import VectorStore, index_post
from egregora.agents.writer.agent import WriterRuntimeContext, write_posts_with_pydantic_agent
from egregora.agents.writer.context import _load_profiles_context, build_rag_context_for_prompt
from egregora.agents.writer.formatting import _build_conversation_markdown, _load_freeform_memory
from egregora.agents.writer.handlers import (
    _handle_annotate_conversation_tool,
    _handle_generate_banner_tool,
    _handle_read_profile_tool,
    _handle_search_media_tool,
    _handle_write_post_tool,
    _handle_write_profile_tool,
)
from egregora.config import ModelConfig, load_mkdocs_config
from egregora.config.loader import create_default_config
from egregora.prompt_templates import WriterPromptTemplate
from egregora.rendering.base import output_registry

if TYPE_CHECKING:
    from google import genai
    from google.genai import types as genai_types
    from ibis.expr.types import Table

    from egregora.storage import JournalStorage, PostStorage, ProfileStorage

logger = logging.getLogger(__name__)


def _create_storage_implementations(
    site_root: Path,
) -> tuple[PostStorage, ProfileStorage, JournalStorage]:
    """Create storage implementations for the given site root.

    This factory function hides the concrete storage implementation from agents.
    Currently uses MkDocs filesystem storage, but could be swapped for database
    or S3 storage without changing agent code.

    Args:
        site_root: Root directory for the site

    Returns:
        Tuple of (PostStorage, ProfileStorage, JournalStorage) implementations

    """
    # Import concrete implementations at runtime (not at type-check time)
    from egregora.storage.mkdocs import MkDocsJournalStorage, MkDocsPostStorage, MkDocsProfileStorage

    return (
        MkDocsPostStorage(site_root),
        MkDocsProfileStorage(site_root),
        MkDocsJournalStorage(site_root),
    )


@dataclass
class WriterConfig:
    """Configuration for the writer functions.

    All embeddings use fixed 768-dimension output.
    """

    output_dir: Path = Path("output/posts")
    profiles_dir: Path = Path("output/profiles")
    rag_dir: Path = Path("output/rag")
    site_root: Path | None = None  # For custom prompt overrides in {site_root}/.egregora/prompts/
    model_config: ModelConfig | None = None
    enable_rag: bool = True
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None


MAX_CONVERSATION_TURNS = 10


def _memes_enabled(site_config: dict[str, Any]) -> bool:
    """Return True when meme helper text should be appended to the prompt."""
    if not isinstance(site_config, dict):
        return False
    writer_settings = site_config.get("writer")
    if not isinstance(writer_settings, dict):
        return False
    return bool(writer_settings.get("enable_memes", False))


def load_site_config(output_dir: Path) -> dict[str, Any]:
    """Load egregora configuration from mkdocs.yml if it exists.

    Reads the `extra.egregora` section from mkdocs.yml in the output directory.
    Returns empty dict if no config found.

    Args:
        output_dir: Output directory (will look for mkdocs.yml in parent/root)

    Returns:
        Dict with egregora config (writer_prompt, rag settings, etc.)

    """
    config, mkdocs_path = load_mkdocs_config(output_dir)
    if not mkdocs_path:
        logger.debug("No mkdocs.yml found, using default config")
        return {}
    egregora_config = config.get("extra", {}).get("egregora", {})
    logger.info("Loaded site config from %s", mkdocs_path)
    return egregora_config


def load_markdown_extensions(output_dir: Path) -> str:
    """Load markdown_extensions section from mkdocs.yml and format for LLM.

    The LLM understands these extension names and knows how to use them.
    We just pass the YAML config directly.

    Args:
        output_dir: Output directory (will look for mkdocs.yml in parent/root)

    Returns:
        Formatted YAML string with markdown_extensions section

    """
    config, mkdocs_path = load_mkdocs_config(output_dir)
    if not mkdocs_path:
        logger.debug("No mkdocs.yml found, no custom markdown extensions")
        return ""
    extensions = config.get("markdown_extensions", [])
    if not extensions:
        return ""
    yaml_section = yaml.dump(
        {"markdown_extensions": extensions}, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    logger.info("Loaded %s markdown extensions from %s", len(extensions), mkdocs_path)
    return yaml_section


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


def _process_tool_calls(  # noqa: C901, PLR0913
    candidate: genai_types.Candidate,
    output_dir: Path,
    profiles_dir: Path,
    saved_posts: list[str],
    saved_profiles: list[str],
    client: genai.Client,
    rag_dir: Path,
    annotations_store: AnnotationStore | None,
    *,
    embedding_model: str,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> tuple[bool, list[genai_types.Content], list[str]]:
    """Process all tool calls from LLM response.

    All embeddings use fixed 768 dimensions.
    """
    has_tool_calls = False
    tool_responses: list[genai_types.Content] = []
    freeform_parts: list[str] = []
    if not candidate or not candidate.content or (not candidate.content.parts):
        return (False, [], [])
    for part in candidate.content.parts:
        function_call = getattr(part, "function_call", None)
        if function_call:
            has_tool_calls = True
            fn_call = function_call
            fn_name = fn_call.name
            fn_args = fn_call.args or {}
            if fn_name == "write_post":
                tool_responses.append(_handle_write_post_tool(fn_args, fn_call, output_dir, saved_posts))
            elif fn_name == "read_profile":
                tool_responses.append(_handle_read_profile_tool(fn_args, fn_call, profiles_dir))
            elif fn_name == "write_profile":
                tool_responses.append(
                    _handle_write_profile_tool(fn_args, fn_call, profiles_dir, saved_profiles)
                )
            elif fn_name == "search_media":
                response = _handle_search_media_tool(
                    fn_args,
                    fn_call,
                    client,
                    rag_dir,
                    embedding_model=embedding_model,
                    retrieval_mode=retrieval_mode,
                    retrieval_nprobe=retrieval_nprobe,
                    retrieval_overfetch=retrieval_overfetch,
                )
                tool_responses.append(response)
            elif fn_name == "annotate_conversation":
                tool_responses.append(_handle_annotate_conversation_tool(fn_args, fn_call, annotations_store))
            elif fn_name == "generate_banner":
                tool_responses.append(_handle_generate_banner_tool(fn_args, fn_call, output_dir))
            continue
        text = getattr(part, "text", "")
        if text:
            freeform_parts.append(text)
    return (has_tool_calls, tool_responses, freeform_parts)


def _index_posts_in_rag(saved_posts: list[str], rag_dir: Path, *, embedding_model: str) -> None:
    """Index newly created posts in RAG system.

    All embeddings use fixed 768 dimensions.
    """
    if not saved_posts:
        return
    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        for post_path in saved_posts:
            index_post(Path(post_path), store, embedding_model=embedding_model)
        logger.info("Indexed %s new posts in RAG", len(saved_posts))
    except PromptTooLargeError:
        raise
    except Exception:
        logger.exception("Failed to index posts in RAG")


def _write_posts_for_window_pydantic(
    table: Table,
    start_time: datetime,
    end_time: datetime,
    client: genai.Client,
    config: WriterConfig | None = None,
) -> dict[str, list[str]]:
    """Pydantic AI backend: Let LLM analyze window's messages using Pydantic AI.

    This is the new implementation using Pydantic AI for type safety and observability.
    Automatically traces to Logfire if LOGFIRE_TOKEN is set.

    Args:
        table: Table with messages for the period (already enriched)
        start_time: Start timestamp of the window
        end_time: End timestamp of the window
        client: Gemini client for embeddings
        config: Writer configuration object

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths

    """
    if config is None:
        config = WriterConfig()
    if table.count().execute() == 0:
        return {"posts": [], "profiles": []}
    model_config = ModelConfig() if config.model_config is None else config.model_config
    writer_model = model_config.get_model("writer")
    embedding_model = model_config.get_model("embedding")
    annotations_store = AnnotationStore(config.rag_dir / "annotations.duckdb")
    messages_table = table.to_pyarrow()
    conversation_md = _build_conversation_markdown(messages_table, annotations_store)
    rag_context = ""
    if config.enable_rag:
        rag_context = build_rag_context_for_prompt(
            conversation_md,
            config.rag_dir,
            client,
            embedding_model=embedding_model,
            retrieval_mode=config.retrieval_mode,
            retrieval_nprobe=config.retrieval_nprobe,
            retrieval_overfetch=config.retrieval_overfetch,
            use_pydantic_helpers=True,
        )
    profiles_context = _load_profiles_context(table, config.profiles_dir)
    freeform_memory = _load_freeform_memory(config.rag_dir)
    active_authors = get_active_authors(table)
    site_config = load_site_config(config.output_dir)
    custom_writer_prompt = site_config.get("writer_prompt", "")
    meme_help_enabled = _memes_enabled(site_config)
    markdown_extensions_yaml = load_markdown_extensions(config.output_dir)
    markdown_features_section = ""
    if markdown_extensions_yaml:
        markdown_features_section = f"\n## Available Markdown Features\n\nThis MkDocs site has the following extensions configured:\n\n```yaml\n{markdown_extensions_yaml}```\n\nUse these features appropriately in your posts. You understand how each extension works.\n"

    # Use site_root from config for custom prompt overrides
    # site_root is where the .egregora/ directory lives
    site_root = config.site_root

    # MODERN (Phase 2): Get EgregoraConfig from WriterConfig's ModelConfig
    if config.model_config is None:
        egregora_config = create_default_config(site_root) if site_root else create_default_config(Path.cwd())
    else:
        # Create a copy so CLI overrides (ModelConfig) can be applied without mutating shared config.
        egregora_config = config.model_config.config.model_copy(deep=True)
        egregora_config.models.writer = writer_model
        egregora_config.models.embedding = embedding_model

    # Create storage implementations (MODERN: Adapter Pattern)
    # Determine site_root for storage (use output_dir parent if site_root not set)
    storage_root = site_root if site_root else config.output_dir.parent
    posts_storage, profiles_storage, journals_storage = _create_storage_implementations(storage_root)

    # Create pre-constructed stores
    rag_store = VectorStore(config.rag_dir / "chunks.parquet")

    # Resolve prompts directory
    prompts_dir = (
        storage_root / ".egregora" / "prompts" if (storage_root / ".egregora" / "prompts").is_dir() else None
    )

    # Create runtime context for writer agent (MODERN: uses storage protocols)
    runtime_context = WriterRuntimeContext(
        start_time=start_time,
        end_time=end_time,
        # Storage protocols
        posts=posts_storage,
        profiles=profiles_storage,
        journals=journals_storage,
        # Pre-constructed stores
        rag_store=rag_store,
        annotations_store=annotations_store,
        # LLM client
        client=client,
        # Prompt templates directory
        prompts_dir=prompts_dir,
        # Deprecated (kept for backward compatibility)
        output_dir=config.output_dir,
        profiles_dir=config.profiles_dir,
        rag_dir=config.rag_dir,
        site_root=site_root,
    )

    # Format timestamps for LLM prompt (human-readable)
    date_range = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"

    # Load output format instructions (MkDocs, Hugo, etc.)
    format_instructions = load_format_instructions(site_root)

    # Render prompt using runtime context
    template = WriterPromptTemplate(
        date=date_range,
        markdown_table=conversation_md,
        active_authors=", ".join(active_authors),
        custom_instructions=custom_writer_prompt or "",
        markdown_features=markdown_features_section,
        format_instructions=format_instructions,
        profiles_context=profiles_context,
        rag_context=rag_context,
        freeform_memory=freeform_memory,
        enable_memes=meme_help_enabled,
        site_root=runtime_context.site_root,
    )
    prompt = template.render()

    try:
        saved_posts, saved_profiles = write_posts_with_pydantic_agent(
            prompt=prompt,
            config=egregora_config,
            context=runtime_context,
        )
    except PromptTooLargeError:
        raise
    except Exception as exc:
        logger.exception("Writer agent failed for %s — aborting window", date_range)
        msg = f"Writer agent failed for {date_range}"
        raise RuntimeError(msg) from exc
    if config.enable_rag:
        _index_posts_in_rag(saved_posts, config.rag_dir, embedding_model=embedding_model)
    return {"posts": saved_posts, "profiles": saved_profiles}


def write_posts_for_window(
    table: Table,
    start_time: datetime,
    end_time: datetime,
    client: genai.Client,
    config: WriterConfig | None = None,
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
        start_time: Start timestamp of the window
        end_time: End timestamp of the window
        client: Gemini client for embeddings
        config: Writer configuration object

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths

    Environment Variables:
        LOGFIRE_TOKEN: Optional, enables Logfire observability

    Examples:
        >>> writer_config = WriterConfig()
        >>> start = datetime(2025, 1, 1, 0, 0)
        >>> end = datetime(2025, 1, 1, 23, 59)
        >>> result = write_posts_for_window(table, start, end, client, writer_config)

    """
    if config is None:
        config = WriterConfig()
    logger.info("Using Pydantic AI backend for writer")
    return _write_posts_for_window_pydantic(
        table=table, start_time=start_time, end_time=end_time, client=client, config=config
    )
