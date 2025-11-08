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
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import yaml
from slugify import slugify

from egregora.agents.model_limits import PromptTooLargeError
from egregora.agents.tools.annotations import AnnotationStore
from egregora.agents.tools.profiler import get_active_authors
from egregora.agents.tools.rag import VectorStore, index_post
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
from egregora.agents.writer.writer_agent import WriterRuntimeContext, write_posts_with_pydantic_agent
from egregora.config import ModelConfig, load_mkdocs_config
from egregora.config.loader import create_default_config
from egregora.prompt_templates import WriterPromptTemplate

if TYPE_CHECKING:
    from google import genai
    from google.genai import types as genai_types
    from ibis.expr.types import Table
logger = logging.getLogger(__name__)

FALLBACK_WRITER_MODEL = os.environ.get("EGREGORA_FALLBACK_WRITER_MODEL", "models/gemini-2.0-flash-lite")


@dataclass
class WriterConfig:
    """Configuration for the writer functions.

    All embeddings use fixed 768-dimension output.
    """

    output_dir: Path = Path("output/posts")
    profiles_dir: Path = Path("output/profiles")
    rag_dir: Path = Path("output/rag")
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

    # Determine site root for custom prompt overrides (renderer-agnostic)
    # site_root is where the .egregora/ directory lives
    site_root = config.output_dir.parent if config.output_dir else None

    # MODERN (Phase 2): Get EgregoraConfig from WriterConfig's ModelConfig
    if config.model_config is None:
        egregora_config = create_default_config(site_root) if site_root else create_default_config(Path.cwd())
    else:
        # Create a copy so CLI overrides (ModelConfig) can be applied without mutating shared config.
        egregora_config = config.model_config.config.model_copy(deep=True)
        egregora_config.models.writer = writer_model
        egregora_config.models.embedding = embedding_model

    # Create runtime context for writer agent
    runtime_context = WriterRuntimeContext(
        start_time=start_time,
        end_time=end_time,
        output_dir=config.output_dir,
        profiles_dir=config.profiles_dir,
        rag_dir=config.rag_dir,
        site_root=site_root,
        client=client,
        annotations_store=annotations_store,
    )

    # Format timestamps for LLM prompt (human-readable)
    date_range = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"

    # Render prompt using runtime context
    template = WriterPromptTemplate(
        date=date_range,
        markdown_table=conversation_md,
        active_authors=", ".join(active_authors),
        custom_instructions=custom_writer_prompt or "",
        markdown_features=markdown_features_section,
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
    except Exception:
        logger.exception("Writer agent failed for %s — falling back to single-post summary", date_range)
        fallback_result = _generate_fallback_post(
            conversation_markdown=conversation_md,
            profiles_context=profiles_context,
            start_time=start_time,
            end_time=end_time,
            output_dir=config.output_dir,
            client=client,
            model_name=FALLBACK_WRITER_MODEL,
        )
        if config.enable_rag:
            _index_posts_in_rag(fallback_result["posts"], config.rag_dir, embedding_model=embedding_model)
        return fallback_result
    if config.enable_rag:
        _index_posts_in_rag(saved_posts, config.rag_dir, embedding_model=embedding_model)
    return {"posts": saved_posts, "profiles": saved_profiles}


def _generate_fallback_post(
    *,
    conversation_markdown: str,
    profiles_context: str,
    start_time: datetime,
    end_time: datetime,
    output_dir: Path,
    client: genai.Client,
    model_name: str,
) -> dict[str, list[str]]:
    """Generate a single markdown post when the structured writer agent fails."""
    from google.genai import types as genai_types  # Local import to avoid optional dependency issues

    output_dir.mkdir(parents=True, exist_ok=True)
    window_label = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"
    prompt_lines = [
        "You are a reliable blog writer tasked with producing ONE markdown article summarizing a conversation window.",
        "Requirements:",
        "1. ALWAYS include valid YAML front matter at the top with keys: title, date, slug, tags.",
        f"2. Date must be {start_time:%Y-%m-%d}.",
        "3. Use friendly, concise prose (600-900 words) with headings and bullet points when useful.",
        "4. Highlight key takeaways, decisions, and action items from the conversation.",
        "5. Include a short 'Highlights' section with 3 bullet points.",
        "6. Do NOT invent information that is not present in the conversation.",
        "",
        f"Conversation window ({window_label}):",
        "```markdown",
        conversation_markdown or "*(conversation not available)*",
        "```",
    ]
    if profiles_context:
        prompt_lines.extend(
            [
                "",
                "Profiles context:",
                "```markdown",
                profiles_context,
                "```",
            ]
        )
    prompt = "\n".join(prompt_lines)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])],
            config=genai_types.GenerateContentConfig(temperature=0.4),
        )
        generated = (response.text or "").strip()
    except Exception as fallback_exc:  # noqa: BLE001
        logger.error("Fallback writer model %s failed: %s", model_name, fallback_exc)
        generated = ""

    if not generated:
        generated = (
            f"# Conversation Summary\n\n"
            f"Window: {window_label}\n\n"
            "The fallback writer could not retrieve model output, so only timestamps are recorded."
        )

    if not generated.lstrip().startswith("---"):
        safe_title = f"Conversation Highlights {start_time:%b %d, %Y}"
        fallback_slug = slugify(f"{start_time:%Y-%m-%d-%H%M}-fallback")
        front_matter = (
            "---\n"
            f'title: "{safe_title}"\n'
            f"date: {start_time:%Y-%m-%d}\n"
            f"slug: {fallback_slug}\n"
            "tags: [fallback]\n"
            "---\n\n"
        )
        generated = front_matter + generated

    filename = f"{window_label}-fallback.md"
    path = output_dir / filename
    path.write_text(generated, encoding="utf-8")
    logger.warning("Fallback writer generated %s", path)
    return {"posts": [str(path)], "profiles": []}


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
