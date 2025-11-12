"""Centralized Pydantic configuration for Egregora (ALPHA VERSION).

This module defines the complete configuration structure for Egregora,
including schemas, loading, and saving.

Benefits:
- Single source of truth for all configuration
- Backend independence (works with Hugo, Astro, etc.)
- Type safety (Pydantic validation at load time)
- No backward compatibility - clean alpha design

Strategy:
- ONLY loads from .egregora/config.yml
- Creates default config if missing
- No mkdocs.yml fallback
- No legacy transformation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

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


class PathsConfig(BaseModel):
    """Site directory paths configuration.

    All paths are relative to site_root (output directory).
    Provides defaults that match the standard .egregora/ structure.
    """

    # .egregora/ internal paths (relative to site_root)
    egregora_dir: str = Field(
        default=".egregora",
        description="Egregora internal directory (contains config, rag, cache)",
    )
    rag_dir: str = Field(
        default=".egregora/rag",
        description="RAG database and embeddings storage",
    )
    cache_dir: str = Field(
        default=".egregora/.cache",
        description="API response cache",
    )
    prompts_dir: str = Field(
        default=".egregora/prompts",
        description="Custom prompt overrides",
    )

    # Content paths (relative to site_root)
    docs_dir: str = Field(
        default="docs",
        description="Documentation/content directory",
    )
    posts_dir: str = Field(
        default="posts",
        description="Blog posts directory",
    )
    profiles_dir: str = Field(
        default="profiles",
        description="Author profiles directory",
    )
    media_dir: str = Field(
        default="docs/media",
        description="Media files (images, videos) directory",
    )
    journal_dir: str = Field(
        default="posts/journal",
        description="Agent execution journals directory",
    )


class OutputConfig(BaseModel):
    """Output format configuration.

    Specifies which output format to use for generated content.
    """

    format: Literal["mkdocs", "hugo"] = Field(
        default="mkdocs",
        description="Output format: 'mkdocs' (default), 'hugo', or future formats (database, s3)",
    )

    mkdocs_config_path: str | None = Field(
        default=None,
        description="Path to mkdocs.yml config file, relative to site root. If None, defaults to '.egregora/mkdocs.yml'",
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
    paths: PathsConfig = Field(
        default_factory=PathsConfig,
        description="Site directory paths (relative to site root)",
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


# ============================================================================
# Configuration Loading and Saving
# ============================================================================


def find_egregora_config(start_dir: Path) -> Path | None:
    """Search upward for .egregora/config.yml.

    Args:
        start_dir: Starting directory for upward search

    Returns:
        Path to .egregora/config.yml if found, else None

    """
    current = start_dir.expanduser().resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / ".egregora" / "config.yml"
        if config_path.exists():
            return config_path
    return None


def load_egregora_config(site_root: Path) -> EgregoraConfig:
    """Load Egregora configuration from .egregora/config.yml.

    SIMPLE: Just load .egregora/config.yml, create if missing.

    Args:
        site_root: Root directory of the site

    Returns:
        Validated EgregoraConfig instance

    Raises:
        ValidationError: If config file contains invalid data

    """
    config_path = site_root / ".egregora" / "config.yml"

    if not config_path.exists():
        logger.info("No .egregora/config.yml found, creating default config")
        return create_default_config(site_root)

    logger.info("Loading config from %s", config_path)

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return EgregoraConfig(**data)
    except yaml.YAMLError:
        logger.exception("Failed to parse %s", config_path)
        logger.warning("Creating default config due to YAML error")
        return create_default_config(site_root)
    except Exception:
        logger.exception("Invalid config in %s", config_path)
        logger.warning("Creating default config due to validation error")
        return create_default_config(site_root)


def create_default_config(site_root: Path) -> EgregoraConfig:
    """Create default .egregora/config.yml and return it.

    Args:
        site_root: Root directory of the site

    Returns:
        EgregoraConfig with all defaults

    """
    config = EgregoraConfig()  # All defaults from Pydantic
    save_egregora_config(config, site_root)
    logger.info("Created default config at %s/.egregora/config.yml", site_root)
    return config


def save_egregora_config(config: EgregoraConfig, site_root: Path) -> Path:
    """Save EgregoraConfig to .egregora/config.yml.

    Creates .egregora/ directory if it doesn't exist.

    Args:
        config: EgregoraConfig instance to save
        site_root: Root directory of the site

    Returns:
        Path to the saved config file

    """
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(exist_ok=True, parents=True)

    config_path = egregora_dir / "config.yml"

    # Export as dict
    data = config.model_dump(exclude_defaults=False, mode="python")

    # Write with nice formatting
    yaml_str = yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

    config_path.write_text(yaml_str, encoding="utf-8")
    logger.debug("Saved config to %s", config_path)

    return config_path


__all__ = [
    # Config schemas
    "EgregoraConfig",
    "EnrichmentConfig",
    "FeaturesConfig",
    "ModelsConfig",
    "OutputConfig",
    "PathsConfig",
    "PipelineConfig",
    "PrivacyConfig",
    "RAGConfig",
    "WriterConfig",
    # Config loading functions
    "create_default_config",
    "find_egregora_config",
    "load_egregora_config",
    "save_egregora_config",
    # Constants
    "DEFAULT_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_BANNER_MODEL",
]
