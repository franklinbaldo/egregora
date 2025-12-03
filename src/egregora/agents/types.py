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
    from egregora.config.settings import RAGSettings
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
    """Immutable dependencies passed to agent tools."""

    resources: WriterResources
    window_start: datetime
    window_end: datetime
    window_label: str
    model_name: str

    @property
    def output_sink(self) -> OutputSink:
        return self.resources.output
