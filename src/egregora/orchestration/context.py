"""Unified pipeline context - split into immutable configuration and mutable state.

This module defines:
1. PipelineConfig: Immutable configuration and paths.
2. PipelineState: Mutable runtime state (clients, connections, caches).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from google import genai

    from egregora.config.settings import EgregoraConfig
    from egregora.data_primitives.protocols import UrlContext
    from egregora.database.duckdb_manager import DuckDBStorageManager
    from egregora.knowledge.annotations import AnnotationStore
    from egregora.knowledge.rag import VectorStore
    from egregora.output_adapters.base import OutputAdapter
    from egregora.utils.cache import EnrichmentCache


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
    storage: DuckDBStorageManager
    enrichment_cache: EnrichmentCache

    # Stores (Optional)
    rag_store: VectorStore | None = None
    annotations_store: AnnotationStore | None = None

    # Output & Adapters (Initialized lazily or updated)
    output_format: OutputAdapter | None = None
    adapter: Any = None  # InputAdapter protocol


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
    def storage(self) -> DuckDBStorageManager:
        return self.state.storage

    @property
    def enrichment_cache(self) -> EnrichmentCache:
        return self.state.enrichment_cache

    @property
    def rag_store(self) -> VectorStore | None:
        return self.state.rag_store

    @property
    def annotations_store(self) -> AnnotationStore | None:
        return self.state.annotations_store

    @property
    def output_format(self) -> OutputAdapter | None:
        return self.state.output_format

    @property
    def url_context(self) -> UrlContext | None:
        return self.config_obj.url_context

    @property
    def adapter(self) -> Any:
        return self.state.adapter

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
        output_format: OutputAdapter,
        url_context: UrlContext | None = None,
    ) -> PipelineContext:
        """Update output format in state and url context in config."""
        self.state.output_format = output_format
        if url_context:
            # Create new config object since it's immutable
            from dataclasses import replace

            new_config = replace(self.config_obj, url_context=url_context)
            return PipelineContext(new_config, self.state)
        return self
