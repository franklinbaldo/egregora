"""Pydantic schemas for .egregora/config.yml configuration.

This module defines the configuration structure for the .egregora/ directory,
which replaces settings previously stored in mkdocs.yml extra.egregora.

Migration from mkdocs.yml:
- Old: mkdocs.yml extra.egregora.models.writer
- New: .egregora/config.yml models.writer

Benefits:
- Backend independence (works with Hugo, Astro, etc.)
- User customization (separated from rendering config)
- Type safety (Pydantic validation at load time)
- Custom prompts (.egregora/prompts/ overrides)
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Default models
DEFAULT_MODEL = "google-gla:gemini-flash-latest"
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
DEFAULT_BANNER_MODEL = "models/gemini-2.5-flash-image"

# Model naming conventions
PydanticModelName = Annotated[
    str,
    "Pydantic-AI provider-prefixed model id (e.g., 'google-gla:gemini-flash-latest')",
]
GoogleModelName = Annotated[
    str,
    "Google Generative AI SDK model id (e.g., 'models/gemini-embedding-001')",
]


class ModelsConfig(BaseModel):
    """LLM model configuration for different tasks.

    - Pydantic-AI agents expect provider-prefixed IDs like ``google-gla:gemini-flash-latest``
    - Direct Google GenAI SDK calls expect ``models/<name>`` identifiers
    """

    # Text generation agents (all default to DEFAULT_MODEL, pydantic naming)
    writer: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for blog post generation (pydantic-ai format)",
    )
    enricher: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for URL/text enrichment (pydantic-ai format)",
    )
    enricher_vision: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for image/video enrichment (pydantic-ai format)",
    )
    ranking: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for post ranking (pydantic-ai format)",
    )
    editor: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for interactive post editing (pydantic-ai format)",
    )

    # Special models with their own defaults (direct Gemini API usage)
    embedding: GoogleModelName = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="Model for vector embeddings (Google GenAI format: models/...)",
    )
    banner: GoogleModelName = Field(
        default=DEFAULT_BANNER_MODEL,
        description="Model for banner/cover image generation (Google GenAI format)",
    )


class RAGConfig(BaseModel):
    """Retrieval-Augmented Generation (RAG) configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable RAG for writer agent",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top results to retrieve",
    )
    min_similarity: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for results",
    )
    mode: Literal["ann", "exact"] = Field(
        default="ann",
        description="Retrieval mode: 'ann' (fast, approximate) or 'exact' (slow, precise)",
    )
    nprobe: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="ANN search quality parameter (higher = better quality, slower)",
    )
    overfetch: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Overfetch multiplier for ANN candidate pool",
    )


class WriterConfig(BaseModel):
    """Blog post writer configuration."""

    custom_instructions: str | None = Field(
        default=None,
        description="Custom instructions to guide the writer agent",
    )
    # REMOVED (Phase 3): enable_meme_generation - never accessed
    # REMOVED (Phase 3): enable_banners - never accessed (controlled by API key availability)


class PrivacyConfig(BaseModel):
    """Privacy and data protection settings.

    .. note::
       Currently all privacy features (anonymization, PII detection) are always enabled.
       This config section is reserved for future configurable privacy controls.
    """

    # REMOVED (Phase 3): anonymization_enabled - never accessed (always enabled)
    # REMOVED (Phase 3): pii_detection_enabled - never accessed (always enabled)
    # REMOVED (Phase 3): opt_out_keywords - never accessed (planned feature)


class EnrichmentConfig(BaseModel):
    """Enrichment settings for URLs and media."""

    enabled: bool = Field(
        default=True,
        description="Enable enrichment pipeline",
    )
    enable_url: bool = Field(
        default=True,
        description="Enrich URLs with LLM-generated descriptions",
    )
    enable_media: bool = Field(
        default=True,
        description="Enrich images/videos with LLM-generated descriptions",
    )
    max_enrichments: int = Field(
        default=50,
        ge=0,
        le=200,
        description="Maximum number of enrichments per run",
    )


class PipelineConfig(BaseModel):
    """Pipeline execution settings."""

    step_size: int = Field(
        default=1,
        ge=1,
        description="Size of each processing window (number of messages, hours, days, etc.)",
    )
    step_unit: Literal["messages", "hours", "days", "bytes"] = Field(
        default="days",
        description="Unit for windowing: 'messages' (count), 'hours'/'days' (time), 'bytes' (max packing)",
    )
    overlap_ratio: float = Field(
        default=0.2,
        ge=0.0,
        le=0.5,
        description="Fraction of window to overlap for context continuity (0.0-0.5, default 0.2 = 20%)",
    )
    max_window_time: int | None = Field(
        default=None,
        ge=1,
        description="Maximum time span per window in hours (optional constraint)",
    )
    timezone: str | None = Field(
        default=None,
        description="Timezone for timestamp parsing (e.g., 'America/New_York')",
    )
    batch_threshold: int = Field(
        default=10,
        ge=1,
        description="Minimum items before batching API calls",
    )
    from_date: str | None = Field(
        default=None,
        description="Start date for filtering (ISO format: YYYY-MM-DD)",
    )
    to_date: str | None = Field(
        default=None,
        description="End date for filtering (ISO format: YYYY-MM-DD)",
    )
    max_prompt_tokens: int = Field(
        default=100_000,
        ge=1_000,
        description="Maximum tokens per prompt (default 100k, even if model supports more). Prevents context overflow and controls costs.",
    )
    use_full_context_window: bool = Field(
        default=False,
        description="Use full model context window (overrides max_prompt_tokens cap)",
    )


class OutputConfig(BaseModel):
    """Output format configuration.

    Specifies which output format to use for generated content.
    """

    format: Literal["mkdocs", "hugo"] = Field(
        default="mkdocs",
        description="Output format: 'mkdocs' (default), 'hugo', or future formats (database, s3)",
    )


class FeaturesConfig(BaseModel):
    """Feature flags for experimental or optional functionality."""

    ranking_enabled: bool = Field(
        default=False,
        description="Enable Elo-based post ranking",
    )
    annotations_enabled: bool = Field(
        default=True,
        description="Enable conversation annotations/threading",
    )


class EgregoraConfig(BaseModel):
    """Root configuration for Egregora.

    This model defines the complete .egregora/config.yml schema.

    Example config.yml:
    ```yaml
    models:
      writer: google-gla:gemini-2.0-flash-exp
      enricher: google-gla:gemini-flash-latest

    rag:
      enabled: true
      top_k: 5
      min_similarity: 0.7

    writer:
      custom_instructions: "Write in a casual, friendly tone"
      enable_banners: true

    privacy:
      anonymization_enabled: true
      pii_detection_enabled: true

    pipeline:
      step_size: 1
      step_unit: days

    output:
      format: mkdocs
    ```
    """

    models: ModelsConfig = Field(
        default_factory=ModelsConfig,
        description="LLM model configuration",
    )
    rag: RAGConfig = Field(
        default_factory=RAGConfig,
        description="RAG configuration",
    )
    writer: WriterConfig = Field(
        default_factory=WriterConfig,
        description="Writer configuration",
    )
    privacy: PrivacyConfig = Field(
        default_factory=PrivacyConfig,
        description="Privacy settings",
    )
    enrichment: EnrichmentConfig = Field(
        default_factory=EnrichmentConfig,
        description="Enrichment settings",
    )
    pipeline: PipelineConfig = Field(
        default_factory=PipelineConfig,
        description="Pipeline settings",
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output format settings",
    )
    features: FeaturesConfig = Field(
        default_factory=FeaturesConfig,
        description="Feature flags",
    )

    model_config = ConfigDict(
        extra="forbid",  # Reject unknown fields
        validate_assignment=True,  # Validate on attribute assignment
    )


__all__ = [
    "EgregoraConfig",
    "EnrichmentConfig",
    "FeaturesConfig",
    "ModelsConfig",
    "OutputConfig",
    "PipelineConfig",
    "PrivacyConfig",
    "RAGConfig",
    "WriterConfig",
]
