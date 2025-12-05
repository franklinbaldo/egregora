"""Shared types and dependencies for the writer agent.

This module isolates data structures to avoid circular imports between agent
composition and capability implementations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.config.settings import EgregoraConfig, RAGSettings
    from egregora.data_primitives.protocols import OutputSink
    from egregora.database.task_store import TaskStore
    from egregora.utils.metrics import UsageTracker
    from egregora.utils.quota import QuotaTracker


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


@dataclass(frozen=True)
class WriterResources:
    """Explicit resources required by the writer agent."""

    output: OutputSink
    annotations_store: AnnotationStore | None
    retrieval_config: RAGSettings
    profiles_dir: Path
    prompts_dir: Path | None
    quota: QuotaTracker | None
    usage: UsageTracker | None
    task_store: TaskStore | None = None
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
    active_authors: list[str] = Field(default_factory=list)
    adapter_content_summary: str = ""
    adapter_generation_instructions: str = ""

    @property
    def output_sink(self) -> OutputSink:
        return self.resources.output
