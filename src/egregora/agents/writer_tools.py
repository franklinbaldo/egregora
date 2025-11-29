"""Standalone tool functions for the writer agent.

These can be tested independently and reused by other agents.

All tools are pure functions that accept explicit dependencies via context objects,
making them easy to test, mock, and reuse without requiring Pydantic-AI machinery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.data_primitives.protocols import OutputSink

logger = logging.getLogger(__name__)


# ============================================================================
# Result Models
# ============================================================================


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


class MediaItem(BaseModel):
    """Media item from RAG search."""

    media_type: str | None = None
    media_path: str | None = None
    original_filename: str | None = None
    description: str | None = None
    similarity: float | None = None


class SearchMediaResult(BaseModel):
    """Result from media search."""

    results: list[MediaItem]


class AnnotationResult(BaseModel):
    """Result from creating an annotation."""

    status: str
    annotation_id: str | None = None
    parent_id: str | None = None
    parent_type: str | None = None


class BannerResult(BaseModel):
    """Result from banner generation."""

    status: str
    path: str | None = None


# ============================================================================
# Context Objects (Dependency Injection)
# ============================================================================


@dataclass(frozen=True)
class ToolContext:
    """Shared context for writer tools.

    Provides explicit dependencies instead of coupling to RunContext.
    """

    output_sink: OutputSink
    window_label: str


@dataclass(frozen=True)
class AnnotationContext:
    """Context for annotation tools."""

    annotations_store: AnnotationStore
    window_label: str


@dataclass(frozen=True)
class BannerContext:
    """Context for banner generation tool."""

    output_sink: OutputSink
    window_label: str


# ============================================================================
# Tool Functions (Pure, Testable)
# ============================================================================


def write_post(
    ctx: ToolContext,
    metadata: dict[str, Any],
    content: str,
) -> WritePostResult:
    """Write a blog post document.

    Pure function - easy to test, mock, and reuse.

    Args:
        ctx: Tool context with dependencies
        metadata: Post metadata (title, slug, date, tags, etc.)
        content: Post markdown content

    Returns:
        WritePostResult with status and document ID

    Example:
        >>> ctx = ToolContext(output_sink=mock_sink, window_label="2024-01-01")
        >>> result = write_post(ctx, {"title": "Test"}, "# Content")
        >>> assert result.status == "success"

    """
    doc = Document(
        content=content,
        type=DocumentType.POST,
        metadata=metadata,
        source_window=ctx.window_label,
    )

    ctx.output_sink.persist(doc)
    logger.info("Writer agent saved post (doc_id: %s)", doc.document_id)
    return WritePostResult(status="success", path=doc.document_id)


def read_profile(ctx: ToolContext, author_uuid: str) -> ReadProfileResult:
    """Read an author profile.

    Pure function - easy to test with mock output_sink.

    Args:
        ctx: Tool context with dependencies
        author_uuid: UUID of the author

    Returns:
        ReadProfileResult with profile content

    Example:
        >>> ctx = ToolContext(output_sink=mock_sink, window_label="2024-01-01")
        >>> result = read_profile(ctx, "author-uuid-123")
        >>> assert isinstance(result.content, str)

    """
    doc = ctx.output_sink.read_document(DocumentType.PROFILE, author_uuid)
    content = doc.content if doc else "No profile exists yet."
    return ReadProfileResult(content=content)


def write_profile(
    ctx: ToolContext,
    author_uuid: str,
    content: str,
) -> WriteProfileResult:
    """Write an author profile.

    Args:
        ctx: Tool context with dependencies
        author_uuid: UUID of the author
        content: Profile markdown content

    Returns:
        WriteProfileResult with status and document ID

    Example:
        >>> ctx = ToolContext(output_sink=mock_sink, window_label="2024-01-01")
        >>> result = write_profile(ctx, "author-uuid-123", "# Bio")
        >>> assert result.status == "success"

    """
    doc = Document(
        content=content,
        type=DocumentType.PROFILE,
        metadata={"uuid": author_uuid},
        source_window=ctx.window_label,
    )
    ctx.output_sink.persist(doc)
    logger.info("Writer agent saved profile (doc_id: %s)", doc.document_id)
    return WriteProfileResult(status="success", path=doc.document_id)


async def search_media(
    query: str,
    top_k: int = 5,
) -> SearchMediaResult:
    """Search for relevant media in the knowledge base.

    Uses RAG to find media documents matching the query.

    Args:
        query: Search query text describing the media
        top_k: Number of results to return (default: 5)

    Returns:
        SearchMediaResult with matching media items

    Example:
        >>> result = await search_media("vacation photos", top_k=3)
        >>> assert len(result.results) <= 3

    """
    try:
        from egregora.rag import RAGQueryRequest, search

        # Execute RAG search
        request = RAGQueryRequest(text=query, top_k=top_k)
        response = await search(request)

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

        logger.info(
            "RAG media search returned %d results for query: %s",
            len(media_items),
            query[:50],
        )
        return SearchMediaResult(results=media_items)

    except (ConnectionError, TimeoutError) as exc:
        logger.warning("RAG backend unavailable for media search: %s", exc)
        return SearchMediaResult(results=[])
    except ValueError as exc:
        logger.warning("Invalid query for media search: %s", exc)
        return SearchMediaResult(results=[])
    except (AttributeError, KeyError) as exc:
        logger.exception("Malformed response from RAG media search: %s", exc)
        return SearchMediaResult(results=[])


def annotate_conversation(
    ctx: AnnotationContext,
    parent_id: str,
    parent_type: str,
    commentary: str,
) -> AnnotationResult:
    """Annotate a message or another annotation with commentary.

    Args:
        ctx: Annotation context with annotation store
        parent_id: ID of the message or annotation being annotated
        parent_type: Must be 'message' or 'annotation'
        commentary: Commentary about the parent entity

    Returns:
        AnnotationResult with annotation details

    Raises:
        RuntimeError: If annotation store is not available

    Example:
        >>> ctx = AnnotationContext(annotations_store=store, window_label="...")
        >>> result = annotate_conversation(ctx, "msg-123", "message", "Great point!")
        >>> assert result.status == "success"

    """
    annotation = ctx.annotations_store.save_annotation(
        parent_id=parent_id,
        parent_type=parent_type,
        commentary=commentary,
    )
    return AnnotationResult(
        status="success",
        annotation_id=annotation.id,
        parent_id=annotation.parent_id,
        parent_type=annotation.parent_type,
    )


def generate_banner(
    ctx: BannerContext,
    post_slug: str,
    title: str,
    summary: str,
) -> BannerResult:
    """Generate a banner image for a post.

    Args:
        ctx: Banner context with output sink
        post_slug: Slug of the post
        title: Post title
        summary: Post summary

    Returns:
        BannerResult with status and path

    Example:
        >>> ctx = BannerContext(output_sink=sink, window_label="...")
        >>> result = generate_banner(ctx, "my-post", "Title", "Summary")
        >>> assert result.status in ("success", "failed")

    """
    from egregora.agents.banner.agent import generate_banner as gen_banner
    from egregora.ops.media import save_media_asset

    # media_dir is not part of OutputSink protocol, but MkDocs adapter has it
    if not hasattr(ctx.output_sink, "media_dir"):
        return BannerResult(status="failed", path="Output sink does not support media storage")

    banner_output_dir = ctx.output_sink.media_dir / "images"  # type: ignore[attr-defined]

    result = gen_banner(post_title=title, post_summary=summary, slug=post_slug)

    if result.success and result.document:
        banner_path = save_media_asset(result.document, banner_output_dir)

        # Convert absolute path to web-friendly path
        if hasattr(ctx.output_sink, "get_media_url_path"):
            # MkDocs adapter has this helper
            site_root = getattr(ctx.output_sink, "site_root", None)
            if site_root:
                web_path = ctx.output_sink.get_media_url_path(banner_path, site_root)  # type: ignore[attr-defined]
            else:
                web_path = f"/media/images/{banner_path.name}"
        else:
            # Fallback: assume standard structure
            web_path = f"/media/images/{banner_path.name}"

        return BannerResult(status="success", path=web_path)

    return BannerResult(status="failed", path=result.error)
