"""Simple writer: LLM with write_post tool for editorial control.

The LLM decides what's worth writing, how many posts to create, and all metadata.
Uses function calling (write_post tool) to generate 0-N posts per period.

Documentation:
- Multi-Post Generation: docs/features/multi-post.md
- Architecture (Writer): docs/guides/architecture.md#5-writer-writerpy
- Core Concepts (Editorial Control):
  docs/getting-started/concepts.md#editorial-control-llm-decision-making
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    pass
from pathlib import Path

import ibis
import yaml
from google import genai
from google.genai import types as genai_types
from ibis.expr.types import Table
from returns.result import Failure, Success

from egregora.augmentation.profiler import get_active_authors
from egregora.config import ModelConfig, load_mkdocs_config
from egregora.generation.writer.context import (
    RagErrorReason,
    _load_profiles_context,
    _query_rag_for_context,
)

# Import split modules
from egregora.generation.writer.formatting import (
    _build_conversation_markdown,
    _load_freeform_memory,
    _write_freeform_markdown,
)
from egregora.generation.writer.handlers import (
    _handle_annotate_conversation_tool,
    _handle_generate_banner_tool,
    _handle_read_profile_tool,
    _handle_search_media_tool,
    _handle_tool_error,
    _handle_write_post_tool,
    _handle_write_profile_tool,
)
from egregora.generation.writer.tools import _writer_tools
from egregora.knowledge.annotations import AnnotationStore
from egregora.knowledge.rag import VectorStore, index_post
from egregora.prompt_templates import WriterPromptTemplate
from egregora.utils import GeminiBatchClient, call_with_retries_sync

logger = logging.getLogger(__name__)

# Constants
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
    """
    Load egregora configuration from mkdocs.yml if it exists.

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
    logger.info(f"Loaded site config from {mkdocs_path}")
    return egregora_config


def load_markdown_extensions(output_dir: Path) -> str:
    """
    Load markdown_extensions section from mkdocs.yml and format for LLM.

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

    try:
        extensions = config.get("markdown_extensions", [])

        if not extensions:
            return ""

        # Format as YAML for the LLM
        yaml_section = yaml.dump(
            {"markdown_extensions": extensions},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        logger.info(f"Loaded {len(extensions)} markdown extensions from {mkdocs_path}")
        return yaml_section

    except Exception as e:
        logger.warning(f"Could not load markdown extensions from {mkdocs_path}: {e}")
        return ""


def get_top_authors(table: Table, limit: int = 20) -> list[str]:
    """
    Get top N active authors by message count.

    Args:
        table: Table with 'author' column
        limit: Max number of authors (default 20)

    Returns:
        List of author UUIDs (most active first)
    """
    # Filter out system and enrichment entries
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





def _process_tool_calls(  # noqa: PLR0913
    candidate: genai_types.Candidate,
    output_dir: Path,
    profiles_dir: Path,
    saved_posts: list[str],
    saved_profiles: list[str],
    client: genai.Client,
    batch_client: GeminiBatchClient,
    rag_dir: Path,
    annotations_store: AnnotationStore | None,
    *,
    embedding_model: str,
    embedding_output_dimensionality: int = 3072,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> tuple[bool, list[genai_types.Content], list[str]]:
    """Process all tool calls from LLM response."""
    has_tool_calls = False
    tool_responses: list[genai_types.Content] = []
    freeform_parts: list[str] = []

    if not candidate or not candidate.content or not candidate.content.parts:
        return False, [], []

    for part in candidate.content.parts:
        function_call = getattr(part, "function_call", None)

        if function_call:
            has_tool_calls = True
            fn_call = function_call
            fn_name = fn_call.name
            fn_args = fn_call.args or {}

            try:
                if fn_name == "write_post":
                    tool_responses.append(
                        _handle_write_post_tool(fn_args, fn_call, output_dir, saved_posts)
                    )
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
                        batch_client,
                        rag_dir,
                        embedding_model=embedding_model,
                        embedding_output_dimensionality=embedding_output_dimensionality,
                        retrieval_mode=retrieval_mode,
                        retrieval_nprobe=retrieval_nprobe,
                        retrieval_overfetch=retrieval_overfetch,
                    )
                    tool_responses.append(response)
                elif fn_name == "annotate_conversation":
                    tool_responses.append(
                        _handle_annotate_conversation_tool(fn_args, fn_call, annotations_store)
                    )
                elif fn_name == "generate_banner":
                    tool_responses.append(
                        _handle_generate_banner_tool(fn_args, fn_call, output_dir)
                    )
            except Exception as e:
                tool_responses.append(_handle_tool_error(fn_call, fn_name, e))
            continue

        text = getattr(part, "text", "")
        if text:
            freeform_parts.append(text)

    return has_tool_calls, tool_responses, freeform_parts


def _index_posts_in_rag(
    saved_posts: list[str],
    batch_client: GeminiBatchClient,
    rag_dir: Path,
    *,
    embedding_model: str,
    embedding_output_dimensionality: int = 3072,
) -> None:
    """Index newly created posts in RAG system."""
    if not saved_posts:
        return

    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        for post_path in saved_posts:
            index_post(
                Path(post_path),
                batch_client,
                store,
                embedding_model=embedding_model,
                output_dimensionality=embedding_output_dimensionality,
            )
        logger.info(f"Indexed {len(saved_posts)} new posts in RAG")
    except Exception as e:
        logger.error(f"Failed to index posts in RAG: {e}")


def write_posts_for_period(  # noqa: PLR0912, PLR0913, PLR0915
    table: Table,
    period_date: str,
    client: genai.Client,
    batch_client: GeminiBatchClient,
    output_dir: Path = Path("output/posts"),
    profiles_dir: Path = Path("output/profiles"),
    rag_dir: Path = Path("output/rag"),
    model_config: ModelConfig | None = None,
    enable_rag: bool = True,
    embedding_output_dimensionality: int = 3072,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> dict[str, list[str]]:
    """
    Let LLM analyze period's messages, write 0-N posts, and update author profiles.

    The LLM has full editorial control via tools:
    - write_post: Create blog posts with metadata
    - read_profile: Read existing author profiles
    - write_profile: Update author profiles

    RAG system provides context from previous posts for continuity.

    Args:
        table: Table with messages for the period (already enriched)
        period_date: Period identifier (e.g., "2025-01-01")
        client: Gemini client
        output_dir: Where to save posts
        profiles_dir: Where to save author profiles
        rag_dir: Where RAG vector store is saved
        model_config: Model configuration object (contains model selection logic)
        enable_rag: Whether to use RAG for context
        retrieval_mode: "ann" (default) or "exact" for brute-force lookups
        retrieval_nprobe: Override ANN ``nprobe`` depth when ``retrieval_mode='ann'``
        retrieval_overfetch: Candidate multiplier before ANN filters are applied

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths
    """
    # Early return for empty input
    if table.count().execute() == 0:
        return {"posts": [], "profiles": []}

    # Setup
    if model_config is None:
        model_config = ModelConfig()
    model = model_config.get_model("writer")
    embedding_model = model_config.get_model("embedding")
    logger.info("[blue]🧠 Writer model:[/] %s", model)
    logger.info("[blue]📚 Embedding model:[/] %s", embedding_model)

    annotations_store: AnnotationStore | None = None
    try:
        annotations_path = (output_dir.parent / "annotations.duckdb").resolve()
        annotations_store = AnnotationStore(annotations_path)
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Annotation store unavailable (%s). Continuing without annotations.", exc)

    active_authors = get_active_authors(table)
    messages_table = table.to_pyarrow()
    markdown_table = _build_conversation_markdown(messages_table, annotations_store)

    # Query RAG and load profiles for context
    rag_context = ""
    if enable_rag:
        rag_result = _query_rag_for_context(
            table,
            batch_client,
            rag_dir,
            embedding_model=embedding_model,
            embedding_output_dimensionality=embedding_output_dimensionality,
            retrieval_mode=retrieval_mode,
            retrieval_nprobe=retrieval_nprobe,
            retrieval_overfetch=retrieval_overfetch,
        )

        # Handle Result type from returns library
        match rag_result:
            case tuple():
                # Legacy tuple return for backward compatibility (return_records=True)
                rag_context = rag_result[0]
            case Success():
                # Modern Result type - Success case
                context_obj = rag_result.unwrap()
                rag_context = context_obj.text
                logger.info("RAG context retrieved successfully")
            case Failure():
                # Modern Result type - Failure case
                error_reason = rag_result.failure()
                if error_reason == RagErrorReason.NO_HITS:
                    logger.info("No similar previous posts found")
                elif error_reason == RagErrorReason.SYSTEM_ERROR:
                    logger.error("RAG system error - content quality may be degraded")
                else:
                    logger.warning(f"RAG query unsuccessful: {error_reason}")
    profiles_context = _load_profiles_context(table, profiles_dir)

    # Load previous freeform memo (only persisted memory between periods)
    freeform_memory = _load_freeform_memory(output_dir)

    # Load site config and markdown extensions
    site_config = load_site_config(output_dir)
    custom_writer_prompt = site_config.get("writer_prompt", "")
    meme_help_enabled = _memes_enabled(site_config)
    markdown_extensions_yaml = load_markdown_extensions(output_dir)

    markdown_features_section = ""
    if markdown_extensions_yaml:
        markdown_features_section = f"""
## Available Markdown Features

This MkDocs site has the following extensions configured:

```yaml
{markdown_extensions_yaml}```

Use these features appropriately in your posts. You understand how each extension works.
"""

    # Build prompt
    prompt = WriterPromptTemplate(
        date=period_date,
        markdown_table=markdown_table,
        active_authors=", ".join(active_authors),
        custom_instructions=custom_writer_prompt or "",
        markdown_features=markdown_features_section,
        profiles_context=profiles_context,
        rag_context=rag_context,
        freeform_memory=freeform_memory,
        enable_memes=meme_help_enabled,
    ).render()

    # Setup conversation
    config = genai_types.GenerateContentConfig(
        tools=cast(list[genai_types.Tool | Callable[..., Any]], _writer_tools()),
        temperature=0.7,
    )
    messages: list[genai_types.Content] = [
        genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])
    ]
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    # Conversation loop
    for _ in range(MAX_CONVERSATION_TURNS):
        try:
            response = call_with_retries_sync(
                client.models.generate_content,
                model=model,
                contents=messages,
                config=config,
            )
        except Exception as exc:
            logger.error("Writer generation failed: %s", exc)
            raise

        # Check for valid response
        if not response or not response.candidates:
            logger.warning("No candidates in response, ending conversation")
            break

        candidate = response.candidates[0]

        # Process tool calls
        has_tool_calls, tool_responses, freeform_parts = _process_tool_calls(
            candidate,
            output_dir,
            profiles_dir,
            saved_posts,
            saved_profiles,
            client,
            batch_client,
            rag_dir,
            annotations_store,
            embedding_model=embedding_model,
            embedding_output_dimensionality=embedding_output_dimensionality,
            retrieval_mode=retrieval_mode,
            retrieval_nprobe=retrieval_nprobe,
            retrieval_overfetch=retrieval_overfetch,
        )

        # Exit if no more tools to call
        if not has_tool_calls:
            if freeform_parts:
                freeform_content = "\n\n".join(
                    part.strip() for part in freeform_parts if part and part.strip()
                )
                if freeform_content:
                    freeform_path = _write_freeform_markdown(
                        freeform_content, period_date, output_dir
                    )
                    saved_posts.append(str(freeform_path))
            break

        # Continue conversation
        if candidate.content:
            messages.append(candidate.content)
        messages.extend(tool_responses)

    # Index new posts in RAG
    if enable_rag:
        _index_posts_in_rag(
            saved_posts,
            batch_client,
            rag_dir,
            embedding_model=embedding_model,
            embedding_output_dimensionality=embedding_output_dimensionality,
        )

    return {"posts": saved_posts, "profiles": saved_profiles}
