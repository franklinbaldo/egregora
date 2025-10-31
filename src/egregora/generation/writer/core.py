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
import importlib
import json
import logging
import math
import numbers
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Optional, Type, TYPE_CHECKING, cast, Callable

if TYPE_CHECKING:
    import pandas as pd
from datetime import UTC
from functools import lru_cache
from pathlib import Path
from typing import Any

import ibis
import pyarrow as pa
import yaml
from google import genai
from google.genai import types as genai_types
from ibis.expr.types import Table
from pydantic import BaseModel

from ...augmentation.profiler import get_active_authors, read_profile, write_profile
from ...config import ModelConfig, load_mkdocs_config
from ...knowledge.annotations import ANNOTATION_AUTHOR, Annotation, AnnotationStore
from ...knowledge.rag import VectorStore, index_post, query_media, query_similar_posts
from ...orchestration.write_post import write_post
from ...prompt_templates import WriterPromptTemplate
from ...utils import GeminiBatchClient, call_with_retries_sync

# Import split modules
from .formatting import (
    _write_freeform_markdown,
    _load_freeform_memory,
    _build_conversation_markdown,
    _compute_message_id,
    _stringify_value,
)
from .tools import PostMetadata, _writer_tools
from .context import RagContext, RagErrorReason, _query_rag_for_context, _load_profiles_context
from .handlers import (
    _handle_write_post_tool,
    _handle_read_profile_tool,
    _handle_write_profile_tool,
    _handle_search_media_tool,
    _handle_annotate_conversation_tool,
    _handle_tool_error,
)


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


@lru_cache(maxsize=1)
def _pandas_dataframe_type() -> Type[pd.DataFrame] | None:
    """Return the pandas DataFrame type when pandas is available."""

    try:
        pandas_module = importlib.import_module("pandas")
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return None
    return pandas_module.DataFrame


@lru_cache(maxsize=1)
def _pandas_na_singleton() -> Any | None:
    """Return the pandas.NA singleton when pandas is available."""

    try:
        pandas_module = importlib.import_module("pandas")
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return None
    return pandas_module.NA


def _stringify_value(value: Any) -> str:
    """Convert values to safe strings for table rendering."""

    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, pa.Scalar):  # pragma: no branch - defensive conversion
        if not value.is_valid:
            return ""
        return _stringify_value(value.as_py())
    pandas_na = _pandas_na_singleton()
    if pandas_na is not None and value is pandas_na:
        return ""
    if value is getattr(pa, "NA", None):
        return ""
    if isinstance(value, numbers.Real):
        try:
            if math.isnan(value):
                return ""
        except TypeError:  # pragma: no cover - Decimal('NaN') and similar types
            pass
    else:  # pragma: no branch - defensive guard for exotic numeric types
        try:
            if math.isnan(value):
                return ""
        except TypeError:
            pass
    return str(value)


def _escape_table_cell(value: Any) -> str:
    """Escape markdown table delimiters and normalize whitespace."""

    text = _stringify_value(value)
    text = text.replace("|", "\\|")
    return text.replace("\n", "<br>")


def _compute_message_id(row: Any) -> str:
    """Derive a deterministic identifier for a conversation row.

    The helper accepts any object exposing ``get`` and ``items`` (for example,
    :class:`dict` as well as mapping-like table rows). Legacy helpers passed both ``(row_index, row)``
    positional arguments, but that form is no longer accepted because the index
    value is ignored during hash computation. The function is private to this
    module, so no downstream backwards compatibility considerations apply.
    """

    if not (hasattr(row, "get") and hasattr(row, "items")):
        raise TypeError(
            "_compute_message_id expects an object with mapping-style access"
        )

    parts: list[str] = []
    for key in ("msg_id", "timestamp", "author", "message", "content", "text"):
        value = row.get(key)
        normalized = _stringify_value(value)
        if normalized:
            parts.append(normalized)

    if not parts:
        fallback_pairs = []
        for key, value in sorted(row.items()):
            if key in {"row_index", "similarity"}:
                continue
            normalized = _stringify_value(value)
            if normalized:
                fallback_pairs.append(f"{key}={normalized}")
        if fallback_pairs:
            parts.extend(fallback_pairs)
        else:
            parts.append(
                json.dumps(row, sort_keys=True, default=_stringify_value)
            )

    raw = "||".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _format_annotations_for_message(annotations: list[Annotation]) -> str:
    """Return formatted annotation text for inclusion in a table cell."""

    if not annotations:
        return ""

    formatted_blocks: list[str] = []
    for annotation in annotations:
        timestamp = (
            annotation.created_at.astimezone(UTC)
            if annotation.created_at.tzinfo
            else annotation.created_at.replace(tzinfo=UTC)
        )
        timestamp_text = timestamp.isoformat().replace("+00:00", "Z")
        parent_note = (
            f" · parent #{annotation.parent_annotation_id}"
            if getattr(annotation, "parent_annotation_id", None) is not None
            else ""
        )
        commentary = _stringify_value(annotation.commentary)
        formatted_blocks.append(
            f"**Annotation #{annotation.id}{parent_note} — {timestamp_text} ({ANNOTATION_AUTHOR})**"
            f"\n{commentary}"
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


def _table_to_records(
    data: pa.Table | Iterable[Mapping[str, Any]] | Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize heterogeneous tabular inputs into row dictionaries."""

    if isinstance(data, pa.Table):
        column_names = [str(name) for name in data.column_names]
        columns = {
            name: data.column(index).to_pylist()
            for index, name in enumerate(column_names)
        }
        records = [
            {name: columns[name][row_index] for name in column_names}
            for row_index in range(data.num_rows)
        ]
        return records, column_names

    dataframe_type = _pandas_dataframe_type()
    if dataframe_type is not None and isinstance(data, dataframe_type):
        df_column_names = [str(column) for column in data.columns]
        df_records = [{str(k): v for k, v in record.items()} for record in data.to_dict("records")]
        return df_records, df_column_names

    if isinstance(data, Iterable):
        iter_records = [{str(k): v for k, v in row.items()} for row in data]
        iter_column_names: list[str] = []
        for record in iter_records:
            for key in record:
                if key not in iter_column_names:
                    iter_column_names.append(str(key))
        return iter_records, iter_column_names

    raise TypeError("Unsupported data source for markdown rendering")


def _build_conversation_markdown(
    data: pa.Table | Iterable[Mapping[str, Any]] | Sequence[Mapping[str, Any]],
    annotations_store: AnnotationStore | None,
) -> str:
    """Render conversation rows into markdown with inline annotations."""

    records, column_order = _table_to_records(data)
    if not records:
        return ""

    rows = [dict(record) for record in records]

    if "msg_id" not in column_order:
        msg_ids = [_compute_message_id(row) for row in rows]
        column_order = ["msg_id", *column_order]
        for row, msg_id in zip(rows, msg_ids, strict=False):
            row["msg_id"] = msg_id
    else:
        for row in rows:
            row["msg_id"] = _stringify_value(row.get("msg_id"))

    annotations_map: dict[str, list[Annotation]] = {}
    if annotations_store is not None:
        ordered_ids = list(dict.fromkeys(row["msg_id"] for row in rows))
        annotations_map = {
            msg_id: annotations_store.list_annotations_for_message(msg_id)
            for msg_id in ordered_ids
        }

    message_column = next(
        (candidate for candidate in ("message", "content", "text") if candidate in column_order),
        None,
    )

    if message_column:
        for row in rows:
            row[message_column] = _merge_message_and_annotations(
                row.get(message_column), annotations_map.get(row["msg_id"], [])
            )
    elif annotations_map:
        for row in rows:
            row["annotations"] = _format_annotations_for_message(
                annotations_map.get(row["msg_id"], [])
            )
        if "annotations" not in column_order:
            column_order.append("annotations")

    headers = [str(column) for column in column_order]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]

    for row in rows:
        cells = [_escape_table_cell(row.get(column)) for column in headers]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


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
def _writer_tools() -> Sequence[genai_types.Tool]:
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




def _handle_write_post_tool(
    fn_args: dict[str, Any], fn_call: genai_types.FunctionCall, output_dir: Path, saved_posts: list[str]
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


def _handle_read_profile_tool(fn_args: dict[str, Any], fn_call: genai_types.FunctionCall, profiles_dir: Path) -> genai_types.Content:
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
    fn_args: dict[str, Any], fn_call: genai_types.FunctionCall, profiles_dir: Path, saved_profiles: list[str]
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


def _handle_search_media_tool(  # noqa: PLR0913
    fn_args: dict[str, Any],
    fn_call: genai_types.FunctionCall,
    batch_client: GeminiBatchClient,
    rag_dir: Path,
    *,
    embedding_model: str,
    embedding_output_dimensionality: int = 3072,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> genai_types.Content:
    """Handle search_media tool call."""
    query = fn_args.get("query", "")
    media_types = fn_args.get("media_types")
    limit = fn_args.get("limit", 5)

    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        results = query_media(
            query=query,
            batch_client=batch_client,
            store=store,
            media_types=media_types,
            top_k=limit,
            min_similarity=0.7,
            embedding_model=embedding_model,
            output_dimensionality=embedding_output_dimensionality,
            retrieval_mode=retrieval_mode,
            retrieval_nprobe=retrieval_nprobe,
            retrieval_overfetch=retrieval_overfetch,
        )

        # Format results for LLM
        result_count = results.count().execute()
        if result_count == 0:
            formatted_results = "No matching media found."
        else:
            formatted_list = []
            results_table = results.execute()
            for _, row in results_table.iterrows():
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
    fn_args: dict[str, Any],
    fn_call: genai_types.FunctionCall,
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
        if not isinstance(parent_raw, str):
            raise ValueError("parent_annotation_id must be a string or None")
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


def _handle_tool_error(fn_call: genai_types.FunctionCall, fn_name: str, error: Exception) -> genai_types.Content:
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


def write_posts_for_period(  # noqa: PLR0913, PLR0915
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
            case _:
                # Modern Result type
                if rag_result.is_success():
                    context_obj = rag_result.unwrap()
                    rag_context = context_obj.text
                    logger.info("RAG context retrieved successfully")
                else:
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
                    freeform_path = _write_freeform_markdown(freeform_content, period_date, output_dir)
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
