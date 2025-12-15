"""Shared types and dependencies for the writer agent.

This module isolates data structures to avoid circular imports between agent
composition and capability implementations.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from egregora.agents.banner.agent import generate_banner
from egregora.data_primitives.document import Document, DocumentType
from egregora.orchestration.persistence import persist_banner_document, persist_profile_document
from egregora.rag import RAGQueryRequest, search

if TYPE_CHECKING:
    from google import genai
    from ibis.expr.types import Table

    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.config.settings import EgregoraConfig, RAGSettings
    from egregora.data_primitives.protocols import OutputSink
    from egregora.database.task_store import TaskStore
    from egregora.output_adapters import OutputSinkRegistry
    from egregora.utils.metrics import UsageTracker

logger = logging.getLogger(__name__)


class PostMetadata(BaseModel):
    """Metadata schema for the write_post tool."""

    title: str
    slug: str
    date: str
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    authors: list[str] = Field(default_factory=list)
    category: str | None = None


class WriterAgentReturn(BaseModel):
    """Final assistant response when the agent finishes."""

    summary: str | None = None
    notes: str | None = None


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


@dataclass(frozen=True)
class WriterResources:
    """Explicit resources required by the writer agent."""

    output: OutputSink
    annotations_store: AnnotationStore | None
    storage: Any | None
    embedding_model: str
    retrieval_config: RAGSettings
    profiles_dir: Path
    journal_dir: Path
    prompts_dir: Path | None
    client: genai.Client | None
    usage: UsageTracker | None
    task_store: TaskStore | None = None
    output_registry: OutputSinkRegistry | None = None
    run_id: uuid.UUID | str | None = None


@dataclass(frozen=True)
class WriterDeps:
    """Immutable dependencies passed to agent tools.

    Note:
        - table and config are reserved for future dynamic system prompt use
        - conversation_xml, active_authors, and adapter fields are pre-calculated
          to avoid expensive recomputation during agent execution
        - All fields with default values are safe to access without null checks

    """

    resources: WriterResources
    window_start: datetime
    window_end: datetime
    window_label: str
    model_name: str
    # Reserved for future dynamic system prompt expansion
    # If used in system prompts, add appropriate null checks
    table: Table | None = None
    config: EgregoraConfig | None = None
    # Pre-calculated context parts that are expensive or needed for signature
    conversation_xml: str = ""
    active_authors: list[str] | None = None
    adapter_content_summary: str = ""
    adapter_generation_instructions: str = ""

    @property
    def output_sink(self) -> OutputSink:
        return self.resources.output

    def write_post(self, metadata: dict, content: str) -> WritePostResult:
        """Write a blog post document."""
        # Fix: Unescape literal newlines that might have been escaped by the LLM
        content = content.replace("\\n", "\n")

        doc = Document(
            content=content,
            type=DocumentType.POST,
            metadata=metadata,
            source_window=self.window_label,
        )

        self.resources.output.persist(doc)
        logger.info("Writer agent saved post (doc_id: %s)", doc.document_id)
        return WritePostResult(status="success", path=doc.document_id)

    def read_profile(self, author_uuid: str) -> ReadProfileResult:
        """Read an author's profile document."""
        doc = self.resources.output.read_document(DocumentType.PROFILE, author_uuid)
        content = doc.content if doc else "No profile exists yet."
        return ReadProfileResult(content=content)

    def write_profile(self, author_uuid: str, content: str) -> WriteProfileResult:
        """Write or update an author's profile."""
        # Fix: Unescape literal newlines
        content = content.replace("\\n", "\n")

        # Fallback: Synchronous write
        doc_id = persist_profile_document(
            self.resources.output,
            author_uuid,
            content,
            source_window=self.window_label,
        )
        return WriteProfileResult(status="success", path=doc_id)

    def search_media(self, query: str, top_k: int = 5) -> SearchMediaResult:
        """Search for relevant media using RAG."""
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
            logger.warning("RAG backend unavailable for media search: %s", exc)
            return SearchMediaResult(results=[])
        except ValueError as exc:
            logger.warning("Invalid query for media search: %s", exc)
            return SearchMediaResult(results=[])
        except (AttributeError, KeyError):
            logger.exception("Malformed response from RAG media search")
            return SearchMediaResult(results=[])

    def annotate(self, parent_id: str, parent_type: str, commentary: str) -> AnnotationResult:
        """Create an annotation on a message or another annotation."""
        if self.resources.annotations_store is None:
            msg = "Annotation store is not configured"
            raise RuntimeError(msg)

        try:
            annotation = self.resources.annotations_store.save_annotation(
                parent_id=parent_id, parent_type=parent_type, commentary=commentary
            )
            return AnnotationResult(
                status="success",
                annotation_id=annotation.id,
                parent_id=annotation.parent_id,
                parent_type=annotation.parent_type,
            )
        except (RuntimeError, ValueError) as exc:
            # We catch broad exceptions here intentionally to prevent a single
            # annotation failure from crashing the entire writer agent process.
            # The agent should be able to continue writing even if one annotation fails.
            logger.warning("Failed to persist annotation, continuing without it: %s", exc)
            return AnnotationResult(
                status="failed",
                annotation_id="annotation-error",
                parent_id=parent_id,
                parent_type=parent_type,
            )

    def generate_banner(self, post_slug: str, title: str, summary: str) -> BannerResult:
        """Generate a banner image for a post (synchronous)."""
        # Fallback: Synchronous generation
        result = generate_banner(post_title=title, post_summary=summary, slug=post_slug)

        if result.success and result.document:
            web_path = persist_banner_document(self.resources.output, result.document)
            return BannerResult(status="success", path=web_path, image_path=web_path)

        return BannerResult(status="failed", error=result.error)
