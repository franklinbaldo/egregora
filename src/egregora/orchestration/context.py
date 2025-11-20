"""Unified pipeline context - single source of truth for runtime state and configuration.

This module consolidates all the fragmented context objects into a single,
comprehensive PipelineContext that flows through the entire pipeline.

Replaces:
- WindowProcessingContext
- PipelineEnvironment
- WriterConfig
- WriterEnvironment
- WriterAgentContext
- EnrichmentRuntimeContext
- AvatarContext

Design Philosophy:
- Configuration (Static): EgregoraConfig embedded
- Pipeline State (Runtime): run_id, timestamps, storage connections
- Resources: Clients, caches, stores
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from google import genai

    from egregora.agents.shared.annotations import AnnotationStore
    from egregora.agents.shared.rag import VectorStore
    from egregora.config.settings import EgregoraConfig
    from egregora.data_primitives.protocols import UrlContext
    from egregora.database.duckdb_manager import DuckDBStorageManager
    from egregora.output_adapters.base import OutputAdapter
    from egregora.utils.cache import EnrichmentCache


@dataclass(frozen=True, slots=True)
class PipelineContext:
    """Unified context object for the entire Egregora pipeline.

    This consolidates all runtime state, configuration, and resources
    into a single object that flows through the pipeline stages.

    Attributes:
        # Core Configuration
        config: The main Egregora configuration

        # Pipeline State
        run_id: Unique identifier for this pipeline run
        start_time: When this pipeline run started
        source_type: Type of input source (whatsapp, slack, etc.)
        input_path: Path to the input file/directory

        # Directory Paths
        output_dir: Root output directory
        site_root: Site root directory (for prompts, config)
        docs_dir: Documentation directory
        posts_dir: Posts output directory
        profiles_dir: Profiles output directory
        media_dir: Media files directory

        # Resources & Clients
        client: Google GenAI client
        storage: DuckDB storage manager
        enrichment_cache: Cache for enrichment results

        # Stores (Optional - created as needed)
        rag_store: Vector store for RAG functionality
        annotations_store: Store for conversation annotations

        # Output & Formatting
        output_format: Output adapter (MkDocs, Hugo, etc.)
        url_context: URL generation context

        # Input Adapter
        adapter: Input adapter instance (for media extraction)

    """

    # Core Configuration
    config: EgregoraConfig

    # Pipeline State
    run_id: UUID
    start_time: datetime
    source_type: str  # "whatsapp", "slack", etc.
    input_path: Path

    # Directory Paths
    output_dir: Path
    site_root: Path | None
    docs_dir: Path
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path

    # Resources & Clients
    client: genai.Client
    storage: DuckDBStorageManager
    enrichment_cache: EnrichmentCache

    # Stores (Optional)
    rag_store: VectorStore | None = None
    annotations_store: AnnotationStore | None = None

    # Output & Formatting
    output_format: OutputAdapter | None = None
    url_context: UrlContext | None = None

    # Input Adapter (for media extraction)
    adapter: Any = None  # InputAdapter protocol

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

    def with_adapter(self, adapter: Any) -> PipelineContext:
        """Create a new context with the input adapter populated."""
        from dataclasses import replace  # noqa: PLC0415

        return replace(self, adapter=adapter)

    def with_output_format(
        self,
        output_format: OutputAdapter,
        url_context: UrlContext | None = None,
    ) -> PipelineContext:
        """Create a new context with output format and URL context populated."""
        from dataclasses import replace  # noqa: PLC0415

        return replace(
            self,
            output_format=output_format,
            url_context=url_context or self.url_context,
        )
