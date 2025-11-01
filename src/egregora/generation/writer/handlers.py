"""Tool call handlers for writer module - execute LLM tool requests."""

import json
import logging
from pathlib import Path
from typing import Any

from google.genai import types as genai_types

from ...augmentation.profiler import read_profile, write_profile
from ...knowledge.annotations import AnnotationStore
from ...knowledge.rag import VectorStore, query_media
from ...orchestration.write_post import write_post
from ...utils import GeminiBatchClient
from ..banner import generate_banner_for_post
from .formatting import _stringify_value

logger = logging.getLogger(__name__)


def _handle_write_post_tool(
    fn_args: dict[str, Any],
    fn_call: genai_types.FunctionCall,
    output_dir: Path,
    saved_posts: list[str],
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


def _handle_read_profile_tool(
    fn_args: dict[str, Any], fn_call: genai_types.FunctionCall, profiles_dir: Path
) -> genai_types.Content:
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
    fn_args: dict[str, Any],
    fn_call: genai_types.FunctionCall,
    profiles_dir: Path,
    saved_profiles: list[str],
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

    parent_id = _stringify_value(fn_args.get("parent_id"))
    parent_type = _stringify_value(fn_args.get("parent_type"))
    commentary = _stringify_value(fn_args.get("commentary"))

    annotation = annotations_store.save_annotation(
        parent_id,
        parent_type,
        commentary,
    )

    response_payload = {
        "status": "ok",
        "annotation_id": annotation.id,
        "parent_id": annotation.parent_id,
        "parent_type": annotation.parent_type,
        "created_at": annotation.created_at.isoformat(),
        "author": annotation.author,
    }

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


def _handle_generate_banner_tool(
    fn_args: dict[str, Any],
    fn_call: genai_types.FunctionCall,
    output_dir: Path,
) -> genai_types.Content:
    """Handle generate_banner tool call."""
    post_slug = fn_args.get("post_slug", "")
    title = fn_args.get("title", "")
    summary = fn_args.get("summary", "")

    try:
        # Generate banner image for the post
        banner_path = generate_banner_for_post(
            post_title=title,
            post_summary=summary,
            output_dir=output_dir / "media" / "banners",
            slug=post_slug,
        )

        if banner_path:
            # Return relative path for use in post frontmatter
            relative_path = f"../media/banners/{banner_path.name}"
            logger.info(f"Banner generated at: {relative_path}")
            return genai_types.Content(
                role="user",
                parts=[
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            id=getattr(fn_call, "id", None),
                            name="generate_banner",
                            response={
                                "status": "success",
                                "banner_path": relative_path,
                                "message": f"Banner generated successfully for '{title}'",
                            },
                        )
                    )
                ],
            )
        else:
            logger.warning(f"Banner generation returned None for post: {title}")
            return genai_types.Content(
                role="user",
                parts=[
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            id=getattr(fn_call, "id", None),
                            name="generate_banner",
                            response={
                                "status": "failed",
                                "message": "Banner generation did not produce an image",
                            },
                        )
                    )
                ],
            )
    except Exception as e:
        logger.error(f"Failed to generate banner for {title}: {e}")
        return genai_types.Content(
            role="user",
            parts=[
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        id=getattr(fn_call, "id", None),
                        name="generate_banner",
                        response={"status": "error", "error": str(e)},
                    )
                )
            ],
        )


def _handle_tool_error(
    fn_call: genai_types.FunctionCall, fn_name: str, error: Exception
) -> genai_types.Content:
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
