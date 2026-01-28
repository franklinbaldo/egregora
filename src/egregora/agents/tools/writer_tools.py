"""Standalone writer agent tool implementations.

This module contains pure, testable functions for writer agent tools.
Tools are extracted from inner functions to enable:
- Unit testing without full Pydantic-AI agent setup
- Reusability across different agents
- Clear dependency injection via context objects
- Reduced coupling to agent internals

Each tool function accepts an explicit context object containing its dependencies,
making it easy to test with mocks and reuse in different contexts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

import duckdb
from pydantic import BaseModel
from pydantic_ai import ModelRetry

from egregora.agents.banner.agent import generate_banner
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.text import InvalidInputError, slugify
from egregora.orchestration.persistence import persist_banner_document, persist_profile_document
from egregora.output_sinks.exceptions import DocumentNotFoundError
from egregora.rag import search
from egregora.rag.models import RAGQueryRequest

if TYPE_CHECKING:
    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.data_primitives.document import OutputSink
    from egregora.database.task_store import TaskStore

logger = logging.getLogger(__name__)

# ==============================================================================
# Result Models
# ==============================================================================


class WritePostResult(BaseModel):
    """Result from writing a post."""

    status: str
    path: str


class ReadProfileResult(BaseModel):
    """Result from reading a profile."""

    content: str


class WriteProfileResult(BaseModel):
    """Result from writing a profile."""

    status: str
    path: str
    image_path: str | None = None
    caption: str | None = None


class MediaItem(BaseModel):
    """Represents a media item from search results."""

    media_type: str | None
    media_path: str | None
    original_filename: str | None
    description: str | None
    similarity: float


class SearchMediaResult(BaseModel):
    """Result from searching media."""

    results: list[MediaItem]


class AnnotationResult(BaseModel):
    """Result from creating an annotation."""

    status: str
    annotation_id: str
    parent_id: str
    parent_type: str


class BannerResult(BaseModel):
    """Result from generating a banner."""

    status: str
    path: str | None = None  # Legacy field
    image_path: str | None = None
    caption: str | None = None
    error: str | None = None


# ==============================================================================
# Context Objects
# ==============================================================================


@dataclass
class ToolContext:
    """Context for basic tool operations."""

    output_sink: OutputSink
    window_label: str
    task_store: TaskStore | None = None


@dataclass
class AnnotationContext:
    """Context for annotation operations."""

    annotations_store: AnnotationStore | None


@dataclass
class BannerContext:
    """Context for banner generation."""

    output_sink: OutputSink
    task_store: TaskStore | None = None


# ==============================================================================
# Tool Implementation Functions
# ==============================================================================


def write_post_impl(ctx: ToolContext, metadata: dict | str, content: str) -> WritePostResult:
    """Write a blog post document.

    Args:
        ctx: Tool context with output sink and window label
        metadata: Post metadata (title, date, tags, etc.) as dict or JSON string
        content: Post content in markdown

    Returns:
        WritePostResult with success status and document path

    """
    # Fix: Handle metadata passed as JSON string (some models do this)
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            logger.warning("Failed to parse metadata JSON string: %s", metadata)
            # Fallback to empty dict or keep as string (but Document expects dict)
            metadata = {"title": "Untitled Post", "raw_metadata": metadata}

    # Fix: Unescape literal newlines that might have been escaped by the LLM
    content = content.replace("\\n", "\n")

    # Enforce strict metadata requirements
    if isinstance(metadata, dict):
        missing_fields = []
        if "title" not in metadata or not metadata["title"]:
            missing_fields.append("title")
        if "tags" not in metadata or not metadata["tags"]:
            missing_fields.append("tags")

        if missing_fields:
            msg = f"Missing required metadata fields: {', '.join(missing_fields)}. Please provide both 'title' and 'tags' (as a list) for the blog post."
            logger.warning(msg)
            raise ModelRetry(msg)

    # Validate and cast metadata to the expected type
    metadata_dict = cast(dict[str, Any], metadata) if isinstance(metadata, dict) else {}

    doc = Document(
        content=content,
        type=DocumentType.POST,
        metadata=metadata_dict,
        source_window=ctx.window_label,
    )

    try:
        ctx.output_sink.persist(doc)
    except Exception as exc:
        msg = f"Failed to persist post document: {exc}"
        logger.exception(msg)
        raise RuntimeError(msg) from exc

    # Verify persistence succeeded
    if not doc.document_id:
        msg = "Post document has no ID after persist - persistence may have failed silently"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info("Writer agent saved post (doc_id: %s)", doc.document_id)
    return WritePostResult(status="success", path=doc.document_id)


def read_profile_impl(ctx: ToolContext, author_uuid: str) -> ReadProfileResult:
    """Read an author's profile document.

    Args:
        ctx: Tool context with output sink
        author_uuid: UUID of the author

    Returns:
        ReadProfileResult with profile content

    """
    try:
        doc = ctx.output_sink.get(DocumentType.PROFILE, author_uuid)
        content = doc.content
        if isinstance(content, bytes):
            content = content.decode("utf-8")
    except DocumentNotFoundError:
        content = "No profile exists yet."
    return ReadProfileResult(content=content)


def write_profile_impl(ctx: ToolContext, author_uuid: str, content: str) -> WriteProfileResult:
    """Write or update an author's profile.

    Args:
        ctx: Tool context with output sink and window label
        author_uuid: UUID of the author
        content: Profile content in markdown

    Returns:
        WriteProfileResult with success status and document path

    """
    # Fix: Unescape literal newlines
    content = content.replace("\\n", "\n")

    # Fallback: Synchronous write
    doc_id = persist_profile_document(
        ctx.output_sink,
        author_uuid,
        content,
        source_window=ctx.window_label,
    )
    return WriteProfileResult(status="success", path=doc_id)


def search_media_impl(query: str, top_k: int = 5) -> SearchMediaResult:
    """Search for relevant media using RAG.

    Args:
        query: Search query describing the media
        top_k: Number of results to return

    Returns:
        SearchMediaResult with matching media items

    Raises:
        ModelRetry: If RAG backend is unavailable (transient error)

    """
    try:
        # Execute RAG search
        request = RAGQueryRequest(text=query, top_k=top_k)
        response = search(request)

        # Convert RAGHit results to MediaItem format
        media_items: list[MediaItem] = []
        for hit in response.hits:
            # Extract media-specific metadata
            metadata = hit.metadata or {}
            media_type = metadata.get("media_type")
            media_path = metadata.get("media_path")
            original_filename = metadata.get("original_filename")

            # Only include media documents
            if media_type:
                media_items.append(
                    MediaItem(
                        media_type=media_type,
                        media_path=media_path,
                        original_filename=original_filename,
                        description=hit.text[:500] if hit.text else None,
                        similarity=hit.score,
                    )
                )

        logger.info("RAG media search returned %d results for query: %s", len(media_items), query[:50])
        return SearchMediaResult(results=media_items)

    except (ConnectionError, TimeoutError, RuntimeError) as exc:
        msg = f"RAG backend unavailable: {exc}. Try writing the post without media lookup."
        logger.warning(msg)
        raise ModelRetry(msg) from exc
    except ValueError as exc:
        logger.warning("Invalid query for media search: %s", exc)
        return SearchMediaResult(results=[])
    except (AttributeError, KeyError):
        logger.exception("Malformed response from RAG media search")
        return SearchMediaResult(results=[])


def annotate_conversation_impl(
    ctx: AnnotationContext, parent_id: str, parent_type: str, commentary: str
) -> AnnotationResult:
    """Create an annotation on a message or another annotation.

    Args:
        ctx: Annotation context with annotations store
        parent_id: ID of the message or annotation being annotated
        parent_type: Either 'message' or 'annotation'
        commentary: Commentary text

    Returns:
        AnnotationResult with annotation details

    Raises:
        RuntimeError: If annotation store is not configured

    """
    if ctx.annotations_store is None:
        msg = "Annotation store is not configured"
        raise RuntimeError(msg)

    if parent_type not in ("message", "annotation"):
        raise ValueError(f"Invalid parent_type: {parent_type}")

    # Cast to literal for mypy
    validated_parent_type = cast("Literal['message', 'annotation']", parent_type)

    try:
        # Persistence to OutputSink is now handled internally by AnnotationStore
        annotation = ctx.annotations_store.save_annotation(
            parent_id=parent_id, parent_type=validated_parent_type, commentary=commentary
        )
        return AnnotationResult(
            status="success",
            annotation_id=annotation.id,
            parent_id=annotation.parent_id,
            parent_type=annotation.parent_type,
        )
    except (RuntimeError, ValueError, OSError, AttributeError, duckdb.Error) as exc:
        # We catch expected persistence exceptions here to prevent a single
        # annotation failure from crashing the entire writer agent process.
        logger.warning("Failed to save annotation: %s", exc)
        return AnnotationResult(
            status="failed",
            annotation_id="annotation-error",
            parent_id=parent_id,
            parent_type=parent_type,
        )


def generate_banner_impl(ctx: BannerContext, post_slug: str, title: str, summary: str) -> BannerResult:
    """Generate a banner image for a post.

    Uses task_store if available for background processing, otherwise runs synchronously.

    Args:
        ctx: Banner context with output sink and optional task store
        post_slug: Slug for the post
        title: Post title
        summary: Post summary

    Returns:
        BannerResult with generation status and path

    """
    if ctx.task_store:
        logger.info("Scheduling background banner generation for %s", post_slug)

        payload = {
            "post_slug": post_slug,
            "title": title,
            "summary": summary,
        }

        task_id = ctx.task_store.enqueue(
            task_type="generate_banner",
            payload=payload,
        )
        logger.info("Scheduled banner generation task: %s", task_id)

        # Predict path
        try:
            slug = slugify(post_slug, max_len=60)
        except InvalidInputError:
            logger.warning("Cannot generate banner placeholder path with invalid slug: %s", post_slug)
            return BannerResult(status="failed", error="Invalid post_slug provided for banner generation.")
        extension = ".jpg"
        filename = f"{slug}{extension}"

        # Create placeholder document for URL prediction
        placeholder_doc = Document(
            content="",
            type=DocumentType.MEDIA,
            metadata={"filename": filename},
            id=filename,
        )

        if ctx.output_sink.url_convention:
            predicted_url = ctx.output_sink.url_convention.canonical_url(
                placeholder_doc, ctx.output_sink.url_context
            )
            predicted_path = predicted_url.lstrip("/")
        else:
            predicted_path = f"media/images/{filename}"

        return BannerResult(status="scheduled", path=predicted_path)

    # Fallback: Synchronous generation
    result = generate_banner(post_title=title, post_summary=summary, slug=post_slug)

    if result.success and result.document:
        web_path = persist_banner_document(ctx.output_sink, result.document)
        return BannerResult(status="success", path=web_path, image_path=web_path)

    return BannerResult(status="failed", error=result.error)
