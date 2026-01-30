"""Unified pipeline context - split into immutable configuration and mutable state.

This module defines:
1. PipelineRunParams: Immutable parameters required to start a run.
2. PipelineConfig: Immutable configuration and paths.
3. PipelineState: Mutable runtime state (clients, connections, caches).
4. PipelineContext: Composite container exposing both configuration and state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from pathlib import Path

    from google import genai

    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.config.settings import EgregoraConfig
    from egregora.data_primitives.document import OutputSink, UrlContext
    from egregora.database.protocols import StorageProtocol
    from egregora.database.task_store import TaskStore
    from egregora.input_adapters.base import InputAdapter
    from egregora.llm.usage import UsageTracker
    from egregora.orchestration.cache import PipelineCache
    from egregora.orchestration.error_boundary import ErrorBoundary
    from egregora.output_sinks import OutputSinkRegistry
    from egregora.rag.embedding_router import EmbeddingRouter


__all__ = [
    "PipelineConfig",
    "PipelineContext",
    "PipelineRunParams",
    "PipelineState",
]


# Canonical run parameter container (single definition to avoid merge artifacts).
@dataclass(frozen=True, slots=True)
class PipelineRunParams:
    """Aggregated parameters required to start a pipeline run."""

    output_dir: Path
    config: EgregoraConfig
    source_type: str
    input_path: Path
    source_key: str | None = None
    client: genai.Client | None = None
    refresh: str | None = None
    is_demo: bool = False
    run_id: UUID = field(default_factory=uuid.uuid4)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    smoke_test: bool = False


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Immutable configuration for the pipeline.

    Contains settings and paths that do not change during execution.
    """

    config: EgregoraConfig
    output_dir: Path
    site_root: Path | None
    docs_dir: Path
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path

    # URL context is largely static configuration
    url_context: UrlContext | None = None
    is_demo: bool = False

    @property
    def enable_enrichment(self) -> bool:
        """Check if enrichment is enabled in config."""
        return self.config.enrichment.enabled

    @property
    def enable_rag(self) -> bool:
        """Check if RAG is enabled in config."""
        return self.config.rag.enabled

    @property
    def writer_model(self) -> str:
        """Get the configured writer model."""
        return self.config.models.writer

    @property
    def enricher_model(self) -> str:
        """Get the configured enricher model."""
        return self.config.models.enricher

    @property
    def embedding_model(self) -> str:
        """Get the configured embedding model."""
        return self.config.models.embedding


@dataclass
class PipelineState:
    """Mutable runtime state for the pipeline.

    Contains resources, clients, and ephemeral state that may be updated
    or re-initialized during execution. Updated for V3 schema.
    """

    # Run Identity
    run_id: UUID
    start_time: datetime
    source_type: str  # "whatsapp", "slack", etc.
    input_path: Path

    # Resources & Clients
    client: genai.Client
    storage: StorageProtocol  # Use protocol instead of concrete implementation
    cache: PipelineCache

    # Stores (Optional)
    annotations_store: AnnotationStore | None = None
    task_store: TaskStore | None = None

    # Pure Content Library Facade
    library: object = None  # Pure ContentLibrary (avoid V2→Pure import)

    # Output & Adapters (Initialized lazily or updated)
    output_sink: OutputSink | None = None  # ISP-compliant: Runtime data operations only
    adapter: InputAdapter | None = None  # InputAdapter instance for source-specific parsing
    usage_tracker: UsageTracker | None = None
    output_registry: OutputSinkRegistry | None = None
    embedding_router: EmbeddingRouter | None = None
    error_boundary: ErrorBoundary | None = None
    smoke_test: bool = False


@dataclass(frozen=True, slots=True)
class PipelineContext:
    """Composite context combining config and state.

    Splits concerns into immutable config and mutable state.
    """

    config_obj: PipelineConfig
    state: PipelineState

    @property
    def config(self) -> EgregoraConfig:
        return self.config_obj.config

    @property
    def run_id(self) -> UUID:
        return self.state.run_id

    @property
    def start_time(self) -> datetime:
        return self.state.start_time

    @property
    def source_type(self) -> str:
        return self.state.source_type

    @property
    def input_path(self) -> Path:
        return self.state.input_path

    @property
    def output_dir(self) -> Path:
        return self.config_obj.output_dir

    @property
    def site_root(self) -> Path | None:
        return self.config_obj.site_root

    @property
    def docs_dir(self) -> Path:
        return self.config_obj.docs_dir

    @property
    def posts_dir(self) -> Path:
        return self.config_obj.posts_dir

    @property
    def profiles_dir(self) -> Path:
        return self.config_obj.profiles_dir

    @property
    def media_dir(self) -> Path:
        return self.config_obj.media_dir

    @property
    def client(self) -> genai.Client:
        return self.state.client

    @property
    def storage(self) -> StorageProtocol:
        """Return storage backend (abstracted via protocol)."""
        return self.state.storage

    @property
    def cache(self) -> PipelineCache:
        return self.state.cache

    @property
    def annotations_store(self) -> AnnotationStore | None:
        return self.state.annotations_store

    @property
    def task_store(self) -> TaskStore | None:
        return self.state.task_store

    @property
    def library(self) -> object:  # Pure ContentLibrary (avoid V2→Pure import)
        return self.state.library

    @property
    def output_sink(self) -> OutputSink | None:
        """Return the output sink for runtime document persistence."""
        return self.state.output_sink

    @property
    def output_registry(self) -> OutputSinkRegistry | None:
        """Return the output adapter registry."""
        return self.state.output_registry

    @property
    def url_context(self) -> UrlContext | None:
        return self.config_obj.url_context

    @property
    def adapter(self) -> InputAdapter | None:
        return self.state.adapter

    @property
    def usage_tracker(self) -> UsageTracker | None:
        return self.state.usage_tracker

    @property
    def embedding_router(self) -> EmbeddingRouter | None:
        return self.state.embedding_router

    @property
    def error_boundary(self) -> ErrorBoundary | None:
        return self.state.error_boundary

    # Forward config properties
    @property
    def enable_enrichment(self) -> bool:
        return self.config_obj.enable_enrichment

    @property
    def enable_rag(self) -> bool:
        return self.config_obj.enable_rag

    @property
    def writer_model(self) -> str:
        return self.config_obj.writer_model

    @property
    def enricher_model(self) -> str:
        return self.config_obj.enricher_model

    @property
    def embedding_model(self) -> str:
        return self.config_obj.embedding_model

    def with_adapter(self, adapter: InputAdapter) -> PipelineContext:
        """Update adapter in state.

        Args:
            adapter: InputAdapter instance for source-specific parsing

        Returns:
            Self for method chaining

        """
        self.state.adapter = adapter
        return self

    def with_output_sink(
        self,
        output_sink: OutputSink,
        url_context: UrlContext | None = None,
    ) -> PipelineContext:
        """Update output sink in state and url context in config.

        Args:
            output_sink: OutputSink implementation for document persistence
            url_context: Optional URL context for canonical URL generation

        """
        self.state.output_sink = output_sink
        if url_context:
            # Create new config object since it's immutable
            new_config = replace(self.config_obj, url_context=url_context)
            return PipelineContext(new_config, self.state)
        return self
