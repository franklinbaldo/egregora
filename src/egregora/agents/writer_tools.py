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

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic_ai import ModelRetry

from egregora.agents.banner.agent import generate_banner
from egregora.data_primitives.document import Document, DocumentType
from egregora.orchestration.persistence import persist_banner_document, persist_profile_document
from egregora.rag import search
from egregora.rag.models import RAGQueryRequest

if TYPE_CHECKING:
    from egregora.agents.capabilities import AsyncProfileCapability, BackgroundBannerCapability
    from egregora.database.annotations_store import AnnotationsStore
    from egregora.output_adapters.base import OutputSink

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
    profile_capability: AsyncProfileCapability | None = None


@dataclass
class AnnotationContext:
    """Context for annotation operations."""

    annotations_store: AnnotationsStore | None


@dataclass
class BannerContext:
    """Context for banner generation."""

    output_sink: OutputSink
    banner_capability: BackgroundBannerCapability | None = None


# ==============================================================================
# Tool Implementation Functions
# ==============================================================================


def write_post_impl(ctx: ToolContext, metadata: dict, content: str) -> WritePostResult:
    """Write a blog post document.

    Args:
        ctx: Tool context with output sink and window label
        metadata: Post metadata (title, date, tags, etc.)
        content: Post content in markdown

    Returns:
        WritePostResult with success status and document path

    """
    # Fix: Unescape literal newlines that might have been escaped by the LLM
    content = content.replace("\\n", "\n")

    doc = Document(
        content=content,
        type=DocumentType.POST,
        metadata=metadata,
        source_window=ctx.window_label,
    )

    ctx.output_sink.persist(doc)
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
    doc = ctx.output_sink.read_document(DocumentType.PROFILE, author_uuid)
    content = doc.content if doc else "No profile exists yet."
    return ReadProfileResult(content=content)


def write_profile_impl(ctx: ToolContext, author_uuid: str, content: str) -> WriteProfileResult:
    """Write or update an author's profile.

    If an AsyncProfileCapability is available in the context, this delegates to it.
    Otherwise, it writes directly to the output sink (synchronous fallback).

    Args:
        ctx: Tool context with output sink and window label
        author_uuid: UUID of the author
        content: Profile content in markdown

    Returns:
        WriteProfileResult with success status and document path

    """
    if ctx.profile_capability:
        logger.info("Delegating profile update to async capability for %s", author_uuid)
        return ctx.profile_capability.schedule(author_uuid, content)

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
    except (AttributeError, KeyError) as exc:
        logger.exception("Malformed response from RAG media search: %s", exc)
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

    try:
        annotation = ctx.annotations_store.save_annotation(
            parent_id=parent_id, parent_type=parent_type, commentary=commentary
        )
        return AnnotationResult(
            status="success",
            annotation_id=annotation.id,
            parent_id=annotation.parent_id,
            parent_type=annotation.parent_type,
        )
    except Exception as exc:  # noqa: BLE001 - defensive catch to avoid pipeline aborts
        logger.warning("Failed to persist annotation, continuing without it: %s", exc)
        return AnnotationResult(
            status="failed",
            annotation_id="annotation-error",
            parent_id=parent_id,
            parent_type=parent_type,
        )


def generate_banner_impl(ctx: BannerContext, post_slug: str, title: str, summary: str) -> BannerResult:
    """Generate a banner image for a post.

    If an AsyncBannerCapability is available, delegates to it.
    Otherwise, generates synchronously.

    Args:
        ctx: Banner context with output sink
        post_slug: Slug for the post
        title: Post title
        summary: Post summary

    Returns:
        BannerResult with generation status and path

    """
    if ctx.banner_capability:
        logger.info("Delegating banner generation to async capability for %s", post_slug)
        return ctx.banner_capability.schedule(post_slug, title, summary)

    # Fallback: Synchronous generation
    result = generate_banner(post_title=title, post_summary=summary, slug=post_slug)

    if result.success and result.document:
        web_path = persist_banner_document(ctx.output_sink, result.document)
        return BannerResult(status="success", path=web_path, image_path=web_path)

    return BannerResult(status="failed", error=result.error)
