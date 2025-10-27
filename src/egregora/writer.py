"""Simple writer: LLM with write_post tool for editorial control.

The LLM decides what's worth writing, how many posts to create, and all metadata.
Uses function calling (write_post tool) to generate 0-N posts per period.

Documentation:
- Multi-Post Generation: docs/features/multi-post.md
- Architecture (Writer): docs/guides/architecture.md#5-writer-writerpy
- Core Concepts (Editorial Control): docs/getting-started/concepts.md#editorial-control-llm-decision-making
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from datetime import timezone
from typing import Any

import ibis
import pandas as pd
import yaml
from google import genai
from google.genai import types as genai_types
from ibis.expr.types import Table
from pydantic import BaseModel

from .annotations import ANNOTATION_AUTHOR, Annotation, AnnotationStore
from .genai_utils import call_with_retries
from .model_config import ModelConfig
from .profiler import get_active_authors, read_profile, write_profile
from .prompt_templates import render_writer_prompt
from .rag import VectorStore, index_post, query_media, query_similar_posts
from .site_config import load_mkdocs_config
from .write_post import write_post


def _write_freeform_markdown(content: str, date: str, output_dir: Path) -> Path:
    """Persist freeform LLM responses that skipped tool calls."""

    freeform_dir = output_dir / "freeform"
    freeform_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{date}-freeform"
    candidate_path = freeform_dir / f"{base_name}.md"
    suffix = 1

    while candidate_path.exists():
        suffix += 1
        candidate_path = freeform_dir / f"{base_name}-{suffix}.md"

    normalized_content = content.strip()
    front_matter = "\n".join(
        [
            "---",
            f"title: Freeform Response ({date})",
            f"date: {date}",
            "---",
            "",
            normalized_content,
            "",
        ]
    )

    candidate_path.write_text(front_matter, encoding="utf-8")
    return candidate_path


def _load_freeform_memory(output_dir: Path) -> str:
    """Return the latest freeform memo content (if any)."""

    freeform_dir = output_dir / "freeform"
    if not freeform_dir.exists():
        return ""

    files = sorted(freeform_dir.glob("*.md"))
    if not files:
        return ""

    latest = max(files, key=lambda path: path.stat().st_mtime)
    try:
        return latest.read_text(encoding="utf-8")
    except OSError:
        return ""


def _stringify_value(value: Any) -> str:
    """Convert values to safe strings for table rendering."""

    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        if pd.isna(value):  # type: ignore[call-arg]
            return ""
    except TypeError:
        pass
    return str(value)


def _escape_table_cell(value: Any) -> str:
    """Escape markdown table delimiters and normalize whitespace."""

    text = _stringify_value(value)
    text = text.replace("|", "\\|")
    return text.replace("\n", "<br>")


def _compute_message_id(_: int, row: Mapping[str, Any]) -> str:
    """Derive a deterministic identifier for a conversation row."""

    parts: list[str] = []
    for key in ("msg_id", "timestamp", "author", "message", "content", "text"):
        value = row.get(key)
        normalized = _stringify_value(value)
        if normalized:
            parts.append(f"{key}:{normalized}")
    if not parts:
        serialized = json.dumps(
            {key: _stringify_value(value) for key, value in sorted(row.items())},
            sort_keys=True,
            ensure_ascii=False,
        ).strip()
        if serialized:
            parts.append(serialized)
    if not parts:
        parts.append("<empty-row>")
    raw = "||".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _format_annotations_for_message(annotations: list[Annotation]) -> str:
    """Return formatted annotation text for inclusion in a table cell."""

    if not annotations:
        return ""

    formatted_blocks: list[str] = []
    for annotation in annotations:
        timestamp = (
            annotation.created_at.astimezone(timezone.utc)
            if annotation.created_at.tzinfo
            else annotation.created_at.replace(tzinfo=timezone.utc)
        )
        timestamp_text = timestamp.isoformat().replace("+00:00", "Z")
        parent_note = (
            f" · parent #{annotation.parent_annotation_id}"
            if getattr(annotation, "parent_annotation_id", None) is not None
            else ""
        )
        commentary = _stringify_value(annotation.commentary)
        formatted_blocks.append(
            (
                f"**Annotation #{annotation.id}{parent_note} — {timestamp_text} ({ANNOTATION_AUTHOR})**"
                f"\n{commentary}"
            )
        )

    return "\n\n".join(formatted_blocks)


def _merge_message_and_annotations(message_value: Any, annotations: list[Annotation]) -> str:
    """Append annotation content after the original message text."""

    message_text = _stringify_value(message_value)
    annotations_block = _format_annotations_for_message(annotations)

    if not annotations_block:
        return message_text
    if message_text:
        return f"{message_text}\n\n{annotations_block}"
    return annotations_block


def _build_conversation_markdown(
    dataframe: pd.DataFrame, annotations_store: AnnotationStore | None
) -> tuple[str, pd.DataFrame]:
    """Render conversation rows into markdown with inline annotations."""

    if dataframe.empty:
        return "", dataframe

    df = dataframe.copy()

    if "msg_id" not in df.columns:
        msg_ids = [
            _compute_message_id(index, row)
            for index, row in enumerate(df.to_dict("records"))
        ]
        df.insert(0, "msg_id", msg_ids)
    else:
        df["msg_id"] = df["msg_id"].map(_stringify_value)

    annotations_map: dict[str, list[Annotation]] = {}
    if annotations_store is not None:
        ordered_ids = list(dict.fromkeys(df["msg_id"].tolist()))
        annotations_map = {
            msg_id: annotations_store.list_annotations_for_message(msg_id)
            for msg_id in ordered_ids
        }

    message_column = next(
        (candidate for candidate in ("message", "content", "text") if candidate in df.columns),
        None,
    )

    if message_column:
        df[message_column] = [
            _merge_message_and_annotations(value, annotations_map.get(msg_id, []))
            for value, msg_id in zip(
                df[message_column].tolist(), df["msg_id"].tolist()
            )
        ]
    elif annotations_map:
        df["annotations"] = [
            _format_annotations_for_message(annotations_map.get(msg_id, []))
            for msg_id in df["msg_id"].tolist()
        ]

    headers = [str(column) for column in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]

    for _, row in df.iterrows():
        cells = [_escape_table_cell(row[column]) for column in headers]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines), df


logger = logging.getLogger(__name__)

# Constants
MAX_CONVERSATION_TURNS = 10


class PostMetadata(BaseModel):
    """Metadata schema for write_post tool."""

    title: str
    slug: str
    date: str
    tags: list[str] = []
    summary: str = ""
    authors: list[str] = []
    category: str | None = None


@lru_cache(maxsize=1)
def _writer_tools() -> list[genai_types.Tool]:
    """Return tool definitions compatible with the google.genai SDK."""
    metadata_schema = genai_types.Schema(
        type=genai_types.Type.OBJECT,
        properties={
            "title": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="Engaging post title",
            ),
            "slug": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="URL-friendly slug (lowercase, hyphenated)",
            ),
            "date": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="Publication date YYYY-MM-DD",
            ),
            "tags": genai_types.Schema(
                type=genai_types.Type.ARRAY,
                description="Relevant topic tags",
                items=genai_types.Schema(type=genai_types.Type.STRING),
            ),
            "summary": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="Short summary (1-2 sentences)",
            ),
            "authors": genai_types.Schema(
                type=genai_types.Type.ARRAY,
                description="List of anonymized author UUIDs",
                items=genai_types.Schema(type=genai_types.Type.STRING),
            ),
            "category": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="Optional category slug",
                nullable=True,
            ),
        },
        required=["title", "slug", "date"],
    )

    write_post_decl = genai_types.FunctionDeclaration(
        name="write_post",
        description="Save a blog post with metadata (CMS tool)",
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "content": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Markdown post content",
                ),
                "metadata": metadata_schema,
            },
            required=["content", "metadata"],
        ),
    )

    read_profile_decl = genai_types.FunctionDeclaration(
        name="read_profile",
        description="Read the current profile for an author",
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "author_uuid": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="The anonymized author UUID",
                )
            },
            required=["author_uuid"],
        ),
    )

    write_profile_decl = genai_types.FunctionDeclaration(
        name="write_profile",
        description="Write or update an author's profile",
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "author_uuid": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="The anonymized author UUID",
                ),
                "content": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Profile content in markdown format",
                ),
            },
            required=["author_uuid", "content"],
        ),
    )

    search_media_decl = genai_types.FunctionDeclaration(
        name="search_media",
        description=(
            "Search for relevant media (images, memes, videos, audio) by description or topic. "
            "Returns media that was previously shared in the group conversations. "
            "Use this to find visual content to illustrate your blog posts."
        ),
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "query": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description=(
                        "Natural language search query describing the media you're looking for. "
                        "Examples: 'funny meme about procrastination', 'chart about productivity', "
                        "'image related to AI safety'"
                    ),
                ),
                "media_types": genai_types.Schema(
                    type=genai_types.Type.ARRAY,
                    description=(
                        "Optional filter by media type. Valid types: 'image', 'video', 'audio', 'document'. "
                        "If not specified, searches all media types."
                    ),
                    items=genai_types.Schema(type=genai_types.Type.STRING),
                    nullable=True,
                ),
                "limit": genai_types.Schema(
                    type=genai_types.Type.INTEGER,
                    description="Maximum number of results to return (default: 5)",
                    nullable=True,
                ),
            },
            required=["query"],
        ),
    )

    annotate_conversation_decl = genai_types.FunctionDeclaration(
        name="annotate_conversation",
        description=(
            "Store a private annotation linked to a conversation message so it can be "
            "surfaced automatically during future writing sessions."
        ),
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "msg_id": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Identifier of the conversation message being annotated",
                ),
                "my_commentary": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Commentary to remember for the specified message",
                ),
                "parent_annotation_id": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Optional prior annotation ID that this elaborates on",
                    nullable=True,
                ),
            },
            required=["msg_id", "my_commentary"],
        ),
    )

    return [
        genai_types.Tool(
            function_declarations=[
                write_post_decl,
                read_profile_decl,
                write_profile_decl,
                search_media_decl,
                annotate_conversation_decl,
            ]
        )
    ]


def load_site_config(output_dir: Path) -> dict:
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


def get_top_authors(df: Table, limit: int = 20) -> list[str]:
    """
    Get top N active authors by message count.

    Args:
        df: Table with 'author' column
        limit: Max number of authors (default 20)

    Returns:
        List of author UUIDs (most active first)
    """
    # Filter out system and enrichment entries
    author_counts = (
        df.filter(~df.author.isin(["system", "egregora"]))
        .filter(df.author.notnull())
        .filter(df.author != "")
        .group_by("author")
        .aggregate(count=ibis._.count())
        .order_by(ibis.desc("count"))
        .limit(limit)
    )

    if author_counts.count().execute() == 0:
        return []

    return author_counts.author.execute().tolist()


async def _query_rag_for_context(df: Table, client: genai.Client, rag_dir: Path) -> str:
    """Query RAG system for similar previous posts."""
    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        similar_posts = await query_similar_posts(df, client, store, top_k=5, deduplicate=True)

        if similar_posts.count().execute() == 0:
            logger.info("No similar previous posts found")
            return ""

        post_count = similar_posts.count().execute()
        logger.info(f"Found {post_count} similar previous posts")
        rag_context = "\n\n## Related Previous Posts (for continuity and linking):\n"
        rag_context += (
            "You can reference these posts in your writing to maintain conversation continuity.\n\n"
        )

        for row in similar_posts.execute().to_dict("records"):
            rag_context += f"### [{row['post_title']}] ({row['post_date']})\n"
            rag_context += f"{row['content'][:400]}...\n"
            rag_context += f"- Tags: {', '.join(row['tags']) if row['tags'] else 'none'}\n"
            rag_context += f"- Similarity: {row['similarity']:.2f}\n\n"

        return rag_context
    except Exception as e:
        logger.warning(f"RAG query failed: {e}")
        return ""


def _load_profiles_context(df: Table, profiles_dir: Path) -> str:
    """Load profiles for top active authors."""
    top_authors = get_top_authors(df, limit=20)
    if not top_authors:
        return ""

    logger.info(f"Loading profiles for {len(top_authors)} active authors")
    profiles_context = "\n\n## Active Participants (Profiles):\n"
    profiles_context += "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n"

    for author_uuid in top_authors:
        profile_content = read_profile(author_uuid, profiles_dir)

        if profile_content:
            profiles_context += f"### Author: {author_uuid}\n"
            profiles_context += f"{profile_content}\n\n"
        else:
            # No profile yet (first time seeing this author)
            profiles_context += f"### Author: {author_uuid}\n"
            profiles_context += "(No profile yet - first appearance)\n\n"

    logger.info(f"Profiles context: {len(profiles_context)} characters")
    return profiles_context


def _handle_write_post_tool(
    fn_args: dict, fn_call, output_dir: Path, saved_posts: list[str]
) -> genai_types.Content:
    """Handle write_post tool call."""
    content = fn_args.get("content", "")
    metadata = fn_args.get("metadata", {})
    path = write_post(content, metadata, output_dir)
    saved_posts.append(path)

    return genai_types.Content(
        role="user",
        parts=[
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    id=getattr(fn_call, "id", None),
                    name="write_post",
                    response={"status": "success", "path": path},
                )
            )
        ],
    )


def _handle_read_profile_tool(fn_args: dict, fn_call, profiles_dir: Path) -> genai_types.Content:
    """Handle read_profile tool call."""
    author_uuid = fn_args.get("author_uuid", "")
    profile_content = read_profile(author_uuid, profiles_dir)

    return genai_types.Content(
        role="user",
        parts=[
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    id=getattr(fn_call, "id", None),
                    name="read_profile",
                    response={"content": profile_content or "No profile exists yet."},
                )
            )
        ],
    )


def _handle_write_profile_tool(
    fn_args: dict, fn_call, profiles_dir: Path, saved_profiles: list[str]
) -> genai_types.Content:
    """Handle write_profile tool call."""
    author_uuid = fn_args.get("author_uuid", "")
    content = fn_args.get("content", "")
    path = write_profile(author_uuid, content, profiles_dir)
    saved_profiles.append(path)

    return genai_types.Content(
        role="user",
        parts=[
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    id=getattr(fn_call, "id", None),
                    name="write_profile",
                    response={"status": "success", "path": path},
                )
            )
        ],
    )


async def _handle_search_media_tool(
    fn_args: dict,
    fn_call,
    client: genai.Client,
    rag_dir: Path,
) -> genai_types.Content:
    """Handle search_media tool call."""
    query = fn_args.get("query", "")
    media_types = fn_args.get("media_types")
    limit = fn_args.get("limit", 5)

    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        results = await query_media(
            query=query,
            client=client,
            store=store,
            media_types=media_types,
            top_k=limit,
        )

        # Format results for LLM
        result_count = results.count().execute()
        if result_count == 0:
            formatted_results = "No matching media found."
        else:
            formatted_list = []
            results_df = results.execute()
            for _, row in results_df.iterrows():
                media_info = {
                    "media_type": row.get("media_type"),
                    "media_path": row.get("media_path"),
                    "original_filename": row.get("original_filename"),
                    "description": str(row.get("content", ""))[:500],  # Truncate long descriptions
                    "similarity": round(float(row.get("similarity", 0)), 2),
                }
                formatted_list.append(media_info)

            formatted_results = json.dumps(formatted_list, indent=2)

        return genai_types.Content(
            role="user",
            parts=[
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        id=getattr(fn_call, "id", None),
                        name="search_media",
                        response={"results": formatted_results},
                    )
                )
            ],
        )
    except Exception as e:
        logger.error(f"search_media failed: {e}")
        return genai_types.Content(
            role="user",
            parts=[
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        id=getattr(fn_call, "id", None),
                        name="search_media",
                        response={"status": "error", "error": str(e)},
                    )
                )
            ],
        )


def _handle_annotate_conversation_tool(
    fn_args: dict,
    fn_call,
    annotations_store: AnnotationStore | None,
) -> genai_types.Content:
    """Persist annotation data using the AnnotationStore."""

    if annotations_store is None:
        raise RuntimeError("Annotation store is not configured")

    msg_id = _stringify_value(fn_args.get("msg_id"))
    commentary = _stringify_value(fn_args.get("my_commentary"))
    parent_raw = fn_args.get("parent_annotation_id")

    if isinstance(parent_raw, str):
        parent_raw = parent_raw.strip()

    parent_annotation_id: int | None
    if parent_raw in (None, ""):
        parent_annotation_id = None
    else:
        try:
            parent_annotation_id = int(parent_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("parent_annotation_id must be an integer when provided") from exc

    annotation = annotations_store.save_annotation(
        msg_id,
        commentary,
        parent_annotation_id=parent_annotation_id,
    )

    response_payload = {
        "status": "ok",
        "annotation_id": annotation.id,
        "msg_id": annotation.msg_id,
        "created_at": annotation.created_at.isoformat(),
        "author": annotation.author,
    }
    if parent_annotation_id is not None:
        response_payload["parent_annotation_id"] = parent_annotation_id

    return genai_types.Content(
        role="user",
        parts=[
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    id=getattr(fn_call, "id", None),
                    name="annotate_conversation",
                    response=response_payload,
                )
            )
        ],
    )


def _handle_tool_error(fn_call, fn_name: str, error: Exception) -> genai_types.Content:
    """Handle tool execution error."""
    return genai_types.Content(
        role="user",
        parts=[
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    id=getattr(fn_call, "id", None),
                    name=fn_name,
                    response={"status": "error", "error": str(error)},
                )
            )
        ],
        )


async def _process_tool_calls(  # noqa: PLR0913
    candidate,
    output_dir: Path,
    profiles_dir: Path,
    saved_posts: list[str],
    saved_profiles: list[str],
    client: genai.Client,
    rag_dir: Path,
    annotations_store: AnnotationStore | None,
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
                    response = await _handle_search_media_tool(fn_args, fn_call, client, rag_dir)
                    tool_responses.append(response)
                elif fn_name == "annotate_conversation":
                    tool_responses.append(
                        _handle_annotate_conversation_tool(fn_args, fn_call, annotations_store)
                    )
            except Exception as e:
                tool_responses.append(_handle_tool_error(fn_call, fn_name, e))
            continue

        text = getattr(part, "text", "")
        if text:
            freeform_parts.append(text)

    return has_tool_calls, tool_responses, freeform_parts


async def _index_posts_in_rag(saved_posts: list[str], client: genai.Client, rag_dir: Path) -> None:
    """Index newly created posts in RAG system."""
    if not saved_posts:
        return

    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        for post_path in saved_posts:
            await index_post(Path(post_path), client, store)
        logger.info(f"Indexed {len(saved_posts)} new posts in RAG")
    except Exception as e:
        logger.error(f"Failed to index posts in RAG: {e}")


async def write_posts_for_period(  # noqa: PLR0913
    df: Table,
    date: str,
    client: genai.Client,
    output_dir: Path = Path("output/posts"),
    profiles_dir: Path = Path("output/profiles"),
    rag_dir: Path = Path("output/rag"),
    model_config=None,
    enable_rag: bool = True,
) -> dict[str, list[str]]:
    """
    Let LLM analyze period's messages, write 0-N posts, and update author profiles.

    The LLM has full editorial control via tools:
    - write_post: Create blog posts with metadata
    - read_profile: Read existing author profiles
    - write_profile: Update author profiles

    RAG system provides context from previous posts for continuity.

    Args:
        df: Table with messages for the period (already enriched)
        date: Period identifier (e.g., "2025-01-01")
        client: Gemini client
        output_dir: Where to save posts
        profiles_dir: Where to save author profiles
        rag_dir: Where RAG vector store is saved
        model_config: Model configuration object (contains model selection logic)
        enable_rag: Whether to use RAG for context

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths
    """
    # Early return for empty input
    if df.count().execute() == 0:
        return {"posts": [], "profiles": []}

    # Setup
    if model_config is None:
        model_config = ModelConfig()
    model = model_config.get_model("writer")
    logger.info("[blue]🧠 Writer model:[/] %s", model)

    annotations_store: AnnotationStore | None = None
    try:
        annotations_path = (output_dir.parent / "annotations.sqlite3").resolve()
        annotations_store = AnnotationStore(annotations_path)
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Annotation store unavailable (%s). Continuing without annotations.", exc)

    active_authors = get_active_authors(df)
    messages_df = df.execute()
    markdown_table, _ = _build_conversation_markdown(messages_df, annotations_store)

    # Query RAG and load profiles for context
    rag_context = await _query_rag_for_context(df, client, rag_dir) if enable_rag else ""
    profiles_context = _load_profiles_context(df, profiles_dir)

    # Load previous freeform memo (only persisted memory between periods)
    freeform_memory = _load_freeform_memory(output_dir)

    # Load site config and markdown extensions
    site_config = load_site_config(output_dir)
    custom_writer_prompt = site_config.get("writer_prompt", "")
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
    prompt = render_writer_prompt(
        date=date,
        markdown_table=markdown_table,
        active_authors=", ".join(active_authors),
        custom_instructions=custom_writer_prompt or "",
        markdown_features=markdown_features_section,
        profiles_context=profiles_context,
        rag_context=rag_context,
        freeform_memory=freeform_memory,
    )

    # Setup conversation
    config = genai_types.GenerateContentConfig(
        tools=_writer_tools(),
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
            response = await call_with_retries(
                client.aio.models.generate_content,
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
        has_tool_calls, tool_responses, freeform_parts = await _process_tool_calls(
            candidate,
            output_dir,
            profiles_dir,
            saved_posts,
            saved_profiles,
            client,
            rag_dir,
            annotations_store,
        )

        # Exit if no more tools to call
        if not has_tool_calls:
            if freeform_parts:
                freeform_content = "\n\n".join(
                    part.strip() for part in freeform_parts if part and part.strip()
                )
                if freeform_content:
                    freeform_path = _write_freeform_markdown(freeform_content, date, output_dir)
                    saved_posts.append(str(freeform_path))
            break

        # Continue conversation
        messages.append(candidate.content)
        messages.extend(tool_responses)

    # Index new posts in RAG
    if enable_rag:
        await _index_posts_in_rag(saved_posts, client, rag_dir)

    return {"posts": saved_posts, "profiles": saved_profiles}
