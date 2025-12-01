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
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from google import genai

    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.database.protocols import StorageProtocol

from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.protocols import OutputSink, UrlContext
from egregora.output_adapters import OutputAdapterRegistry
from egregora.rag.embedding_router import EmbeddingRouter
from egregora.utils.cache import EnrichmentCache, PipelineCache
from egregora.utils.metrics import UsageTracker
from egregora.utils.quota import QuotaTracker

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
    client: genai.Client | None = None
    refresh: str | None = None
    run_id: UUID = field(default_factory=uuid.uuid4)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))


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

    @property
    def retrieval_mode(self) -> str:
        """Get the configured RAG retrieval mode."""
        return self.config.rag.mode

    @property
    def retrieval_nprobe(self) -> int:
        """Get the configured RAG nprobe value."""
        return self.config.rag.nprobe

    @property
    def retrieval_overfetch(self) -> int:
        """Get the configured RAG overfetch value."""
        return self.config.rag.overfetch


@dataclass(slots=True)
class PipelineState:
    """Mutable runtime state for the pipeline.

    Contains resources, clients, and ephemeral state that may be updated
    or re-initialized during execution.
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

    # Quota tracking
    quota_tracker: QuotaTracker | None = None

    # Output & Adapters (Initialized lazily or updated)
    output_format: OutputSink | None = None  # ISP-compliant: Runtime data operations only
    adapter: Any = None  # InputAdapter protocol
    usage_tracker: UsageTracker | None = None
    output_registry: OutputAdapterRegistry | None = None
    embedding_router: EmbeddingRouter | None = None


@dataclass(frozen=True, slots=True)
class PipelineContext:
    """Composite context combining config and state.

    Maintains backward compatibility while splitting concerns.
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
    def enrichment_cache(self) -> EnrichmentCache:
        """Backward compatibility shim for enrichment cache."""
        return self.state.cache.enrichment

    @property
    def annotations_store(self) -> AnnotationStore | None:
        return self.state.annotations_store

    @property
    def output_format(self) -> OutputSink | None:
        """Return the output sink for runtime document persistence."""
        return self.state.output_format

    @property
    def output_registry(self) -> OutputAdapterRegistry | None:
        """Return the output adapter registry."""
        return self.state.output_registry

    @property
    def url_context(self) -> UrlContext | None:
        return self.config_obj.url_context

    @property
    def adapter(self) -> Any:
        return self.state.adapter

    @property
    def usage_tracker(self) -> UsageTracker | None:
        return self.state.usage_tracker

    @property
    def quota_tracker(self) -> QuotaTracker | None:
        return self.state.quota_tracker

    @property
    def embedding_router(self) -> EmbeddingRouter | None:
        return self.state.embedding_router

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

    @property
    def retrieval_mode(self) -> str:
        return self.config_obj.retrieval_mode

    @property
    def retrieval_nprobe(self) -> int:
        return self.config_obj.retrieval_nprobe

    @property
    def retrieval_overfetch(self) -> int:
        return self.config_obj.retrieval_overfetch

    def with_adapter(self, adapter: Any) -> PipelineContext:
        """Update adapter in state."""
        self.state.adapter = adapter
        return self

    def with_output_format(
        self,
        output_format: OutputSink,
        url_context: UrlContext | None = None,
    ) -> PipelineContext:
        """Update output format in state and url context in config.

        Args:
            output_format: OutputSink implementation for document persistence
            url_context: Optional URL context for canonical URL generation

        """
        self.state.output_format = output_format
        if url_context:
            # Create new config object since it's immutable
            new_config = replace(self.config_obj, url_context=url_context)
            return PipelineContext(new_config, self.state)
        return self
