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

from typing import Literal

from pydantic import BaseModel, Field


class ModelsConfig(BaseModel):
    """LLM model configuration for different tasks.

    All model names use pydantic-ai format: "google-gla:model-name"
    Examples:
    - "google-gla:gemini-2.0-flash-exp"
    - "google-gla:gemini-flash-latest"
    """

    writer: str = Field(
        default="google-gla:gemini-2.0-flash-exp",
        description="Model for blog post generation",
    )
    enricher: str = Field(
        default="google-gla:gemini-flash-latest",
        description="Model for URL/text enrichment",
    )
    enricher_vision: str = Field(
        default="google-gla:gemini-flash-latest",
        description="Model for image/video enrichment",
    )
    embedding: str = Field(
        default="google-gla:gemini-embedding-001",
        description="Model for vector embeddings (RAG)",
    )
    ranking: str | None = Field(
        default=None,
        description="Model for post ranking (optional)",
    )
    editor: str | None = Field(
        default=None,
        description="Model for interactive post editing (optional)",
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
    enable_meme_generation: bool = Field(
        default=False,
        description="Enable meme generation for posts",
    )
    enable_banners: bool = Field(
        default=True,
        description="Enable banner image generation for posts",
    )


class PrivacyConfig(BaseModel):
    """Privacy and data protection settings."""

    anonymization_enabled: bool = Field(
        default=True,
        description="Anonymize author names before LLM processing",
    )
    pii_detection_enabled: bool = Field(
        default=True,
        description="Detect and redact PII (phones, emails, addresses)",
    )
    opt_out_keywords: list[str] = Field(
        default_factory=lambda: ["/egregora opt-out"],
        description="Keywords that trigger opt-out from blog posts",
    )


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

    period: Literal["day", "week", "month"] = Field(
        default="day",
        description="Grouping period for posts",
    )
    timezone: str | None = Field(
        default=None,
        description="Timezone for date parsing (e.g., 'America/New_York')",
    )
    batch_threshold: int = Field(
        default=10,
        ge=1,
        description="Minimum items before batching API calls",
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
    features: FeaturesConfig = Field(
        default_factory=FeaturesConfig,
        description="Feature flags",
    )

    class Config:
        """Pydantic config."""

        extra = "forbid"  # Reject unknown fields
        validate_assignment = True  # Validate on attribute assignment


__all__ = [
    "EgregoraConfig",
    "ModelsConfig",
    "RAGConfig",
    "WriterConfig",
    "PrivacyConfig",
    "EnrichmentConfig",
    "PipelineConfig",
    "FeaturesConfig",
]
