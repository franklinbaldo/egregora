"""Shared types and dependencies for the writer agent.

This module isolates data structures to avoid circular imports between agent
composition and capability implementations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime
    from pathlib import Path

    from google import genai
    from ibis.expr.types import Table

    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.cache import PipelineCache
    from egregora.config.settings import EgregoraConfig, RAGSettings
    from egregora.data_primitives.document import OutputSink
    from egregora.database.task_store import TaskStore
    from egregora.output_adapters import OutputSinkRegistry
    from egregora.utils.metrics import UsageTracker

logger = logging.getLogger(__name__)


class PromptTooLargeError(Exception):
    """Exception raised when a prompt exceeds the model's context window.

    Attributes:
        token_count: The estimated number of tokens in the prompt.
        limit: The context window limit that was exceeded.
        window_label: A human-readable label for the processing window.

    """

    def __init__(self, token_count: int, limit: int, window_label: str = "unknown") -> None:
        self.token_count = token_count
        self.limit = limit
        self.window_label = window_label
        self.message = (
            f"Prompt for {window_label} contains approx {token_count:,} tokens, "
            f"exceeding the {limit:,} token limit."
        )
        super().__init__(self.message)


@dataclass(frozen=True)
class WindowProcessingParams:
    """Parameters for processing a specific time window."""

    window_start: datetime
    window_end: datetime
    window_label: str
    config: EgregoraConfig
    resources: WriterResources
    cache: PipelineCache
    signature: str


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
    quota: Any | None = None


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
