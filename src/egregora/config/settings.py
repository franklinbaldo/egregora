"""Centralized configuration for Egregora (ALPHA VERSION).

This module consolidates ALL configuration code in one place:
- Pydantic models for .egregora/config.yml
- Loading and saving functions
- Runtime dataclasses for function parameters
- Model configuration utilities

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
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

DEFAULT_MODEL = "google-gla:gemini-flash-latest"
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
DEFAULT_BANNER_MODEL = "models/gemini-2.5-flash-image"
EMBEDDING_DIM = 768  # Embedding vector dimensions

# Model naming conventions
PydanticModelName = Annotated[
    str,
    "Pydantic-AI provider-prefixed model id (e.g., 'google-gla:gemini-flash-latest')",
]
GoogleModelName = Annotated[
    str,
    "Google Generative AI SDK model id (e.g., 'models/gemini-embedding-001')",
]


class ModelSettings(BaseModel):
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


class RAGSettings(BaseModel):
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
    min_similarity_threshold: float = Field(
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


class WriterAgentSettings(BaseModel):
    """Blog post writer configuration."""

    custom_instructions: str | None = Field(
        default=None,
        description="Custom instructions to guide the writer agent",
    )
    # REMOVED (Phase 3): enable_meme_generation - never accessed
    # REMOVED (Phase 3): enable_banners - never accessed (controlled by API key availability)


class PrivacySettings(BaseModel):
    """Privacy and data protection settings.

    .. note::
       Currently all privacy features (anonymization, PII detection) are always enabled.
       This config section is reserved for future configurable privacy controls.
    """

    # REMOVED (Phase 3): anonymization_enabled - never accessed (always enabled)
    # REMOVED (Phase 3): pii_detection_enabled - never accessed (always enabled)
    # REMOVED (Phase 3): opt_out_keywords - never accessed (planned feature)


class EnrichmentSettings(BaseModel):
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


from egregora.constants import WindowUnit


class PipelineSettings(BaseModel):
    """Pipeline execution settings."""

    step_size: int = Field(
        default=1,
        ge=1,
        description="Size of each processing window (number of messages, hours, days, etc.)",
    )
    step_unit: WindowUnit = Field(
        default=WindowUnit.DAYS,
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
    max_windows: int | None = Field(
        default=1,
        ge=0,
        description="Maximum windows to process per run (1=single window, 0=all windows, None=all)",
    )
    checkpoint_enabled: bool = Field(
        default=False,
        description="Enable incremental processing with checkpoints (opt-in). Default: always rebuild from scratch for simplicity.",
    )


class PathsSettings(BaseModel):
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


class OutputSettings(BaseModel):
    """Output format configuration.

    Specifies which output format to use for generated content.
    """

    format: Literal["mkdocs", "hugo", "eleventy-arrow"] = Field(
        default="mkdocs",
        description="Output format: 'mkdocs' (default), 'hugo', or future formats (database, s3)",
    )

    mkdocs_config_path: str | None = Field(
        default=None,
        description="Path to mkdocs.yml config file, relative to site root. If None, defaults to '.egregora/mkdocs.yml'",
    )


class DatabaseSettings(BaseModel):
    """Database configuration for pipeline and observability.

    All values must be valid Ibis connection URIs (e.g. DuckDB, Postgres, SQLite).
    """

    pipeline_db: str = Field(
        default="duckdb:///./.egregora/pipeline.duckdb",
        description=(
            "Pipeline database connection URI (e.g. 'duckdb:///absolute/path.duckdb', "
            "'duckdb:///./.egregora/pipeline.duckdb' for a site-relative file, or "
            "'postgres://user:pass@host:5432/dbname')."
        ),
    )
    runs_db: str = Field(
        default="duckdb:///./.egregora/runs.duckdb",
        description=(
            "Run tracking database connection URI (e.g. 'duckdb:///absolute/runs.duckdb', "
            "'duckdb:///./.egregora/runs.duckdb' for a site-relative file, or "
            "'postgres://user:pass@host:5432/dbname')."
        ),
    )


class ReaderSettings(BaseModel):
    """Reader agent configuration for post evaluation and ranking."""

    enabled: bool = Field(
        default=False,
        description="Enable reader agent for post quality evaluation",
    )
    comparisons_per_post: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of pairwise comparisons per post for ELO ranking",
    )
    k_factor: int = Field(
        default=32,
        ge=16,
        le=64,
        description="ELO K-factor controlling rating volatility (16=stable, 64=volatile)",
    )
    database_path: str = Field(
        default=".egregora/reader.duckdb",
        description="Path to reader database for ELO ratings and comparison history",
    )


class FeaturesSettings(BaseModel):
    """Feature flags for experimental or optional functionality."""

    ranking_enabled: bool = Field(
        default=False,
        description="Enable Elo-based post ranking (deprecated: use reader.enabled instead)",
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
      writer: google-gla:gemini-flash-latest
      enricher: google-gla:gemini-flash-latest

    rag:
      enabled: true
      top_k: 5
      min_similarity_threshold: 0.7

    writer:
      custom_instructions: "Write in a casual, friendly tone"
      enable_banners: true

    privacy:
      anonymization_enabled: true
      pii_detection_enabled: true

    pipeline:
      step_size: 1
      step_unit: days

    database:
      pipeline_db: duckdb:///./.egregora/pipeline.duckdb
      runs_db: duckdb:///./.egregora/runs.duckdb

    output:
      format: mkdocs
    ```
    """

    models: ModelSettings = Field(
        default_factory=ModelSettings,
        description="LLM model configuration",
    )
    rag: RAGSettings = Field(
        default_factory=RAGSettings,
        description="RAG configuration",
    )
    writer: WriterAgentSettings = Field(
        default_factory=WriterAgentSettings,
        description="Writer configuration",
    )
    reader: ReaderSettings = Field(
        default_factory=ReaderSettings,
        description="Reader agent configuration",
    )
    privacy: PrivacySettings = Field(
        default_factory=PrivacySettings,
        description="Privacy settings",
    )
    enrichment: EnrichmentSettings = Field(
        default_factory=EnrichmentSettings,
        description="Enrichment settings",
    )
    pipeline: PipelineSettings = Field(
        default_factory=PipelineSettings,
        description="Pipeline settings",
    )
    paths: PathsSettings = Field(
        default_factory=PathsSettings,
        description="Site directory paths (relative to site root)",
    )
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Database configuration (pipeline and run tracking)",
    )
    output: OutputSettings = Field(
        default_factory=OutputSettings,
        description="Output format settings",
    )
    features: FeaturesSettings = Field(
        default_factory=FeaturesSettings,
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
        raw_config = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to read config from %s: %s", config_path, exc)
        raise

    try:
        data = yaml.safe_load(raw_config) or {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse YAML in %s: %s", config_path, exc)
        raise

    try:
        return EgregoraConfig(**data)
    except ValidationError as exc:
        logger.error("Validation failed for %s: %s", config_path, exc)
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
    data = config.model_dump(exclude_defaults=False, mode="json")

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


# ============================================================================
# Runtime Configuration Dataclasses
# ============================================================================
# These dataclasses are used for function parameters (not persisted to YAML).
# They replace parameter soup (12-16 params → 3-6 params).


from egregora.constants import WindowUnit


@dataclass
class ProcessConfig:
    """Configuration for chat export processing (source-agnostic).

    Replaces long parameter lists (15+ params) with structured config object.
    """

    output_dir: Annotated[Path, "Directory for the generated site"]
    input_file: Annotated[Path | None, "Path to the chat export file (ZIP, JSON, etc.)"] = None
    step_size: Annotated[int, "Size of each processing window"] = 1
    step_unit: Annotated[WindowUnit, "Unit for windowing strategy"] = WindowUnit.DAYS
    overlap_ratio: Annotated[float, "Fraction of window to overlap (0.0-0.5)"] = 0.2
    max_window_time: Annotated[timedelta | None, "Optional maximum time span per window"] = None
    enable_enrichment: Annotated[bool, "Enable LLM enrichment for URLs/media"] = True
    from_date: Annotated[date | None, "Only process messages from this date onwards"] = None
    to_date: Annotated[date | None, "Only process messages up to this date"] = None
    timezone: Annotated[str | None, "Timezone for date parsing"] = None
    gemini_key: Annotated[str | None, "Google Gemini API key"] = None
    model: Annotated[str | None, "Gemini model to use"] = None
    debug: Annotated[bool, "Enable debug logging"] = False
    retrieval_mode: Annotated[str, "Retrieval strategy: 'ann' or 'exact'"] = "ann"
    retrieval_nprobe: Annotated[int | None, "Advanced: DuckDB VSS nprobe for ANN"] = None
    retrieval_overfetch: Annotated[int | None, "Advanced: ANN candidate pool multiplier"] = None
    batch_threshold: Annotated[int, "Minimum items before batching API calls"] = 10
    max_prompt_tokens: Annotated[int, "Maximum tokens per prompt"] = 100_000
    use_full_context_window: Annotated[bool, "Use full model context window"] = False
    max_windows: Annotated[int | None, "Maximum number of windows to process (default 1, 0=all)"] = 1
    checkpoint_enabled: Annotated[bool, "Enable incremental processing (opt-in)"] = False

    @property
    def input_path(self) -> Path:
        """Alias for input_file (source-agnostic naming)."""
        return self.input_file


@dataclass
class WriterRuntimeConfig:
    """Runtime configuration for post writing (not the Pydantic WriterConfig)."""

    posts_dir: Annotated[Path, "Directory to save posts"]
    profiles_dir: Annotated[Path, "Directory to save profiles"]
    rag_dir: Annotated[Path, "Directory for RAG data"]
    model_config: Annotated[object | None, "Model configuration"] = None  # ModelConfig defined below
    enable_rag: Annotated[bool, "Enable RAG"] = True


@dataclass
class MediaEnrichmentContext:
    """Context for media enrichment prompts."""

    media_type: Annotated[str, "The type of media (e.g., 'image', 'video')"]
    media_filename: Annotated[str, "The filename of the media"]
    author: Annotated[str, "The author of the message containing the media"]
    timestamp: Annotated[str, "The timestamp of the message"]
    nearby_messages: Annotated[str, "Messages sent before and after the media"]
    ocr_text: Annotated[str, "Text extracted from the media via OCR"] = ""
    detected_objects: Annotated[str, "Objects detected in the media"] = ""


@dataclass
class EnrichmentRuntimeConfig:
    """Runtime configuration for enrichment operations."""

    client: Annotated[object, "The Gemini client"]
    output_dir: Annotated[Path, "The directory to save enriched data"]
    model: Annotated[str, "The Gemini model to use for enrichment"] = DEFAULT_MODEL


@dataclass
class PipelineEnrichmentConfig:
    """Extended enrichment configuration for pipeline operations.

    Extends basic enrichment config with pipeline-specific settings.
    """

    batch_threshold: int = 10
    max_enrichments: int = 500
    enable_url: bool = True
    enable_media: bool = True

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.batch_threshold < 1:
            msg = f"batch_threshold must be >= 1, got {self.batch_threshold}"
            raise ValueError(msg)
        if self.max_enrichments < 0:
            msg = f"max_enrichments must be >= 0, got {self.max_enrichments}"
            raise ValueError(msg)

    @classmethod
    def from_cli_args(cls, **kwargs: int | bool) -> PipelineEnrichmentConfig:
        """Create config from CLI arguments."""
        return cls(
            batch_threshold=kwargs.get("batch_threshold", 10),
            max_enrichments=kwargs.get("max_enrichments", 500),
            enable_url=kwargs.get("enable_url", True),
            enable_media=kwargs.get("enable_media", True),
        )


# ============================================================================
# Model Configuration Utilities
# ============================================================================

# Model type literal for type checking
ModelType = Literal["writer", "enricher", "enricher_vision", "ranking", "editor", "banner", "embedding"]


def get_model_for_task(
    task: ModelType,
    egregora_config: EgregoraConfig | None = None,
    cli_override: str | None = None,
) -> str:
    """Get model name for a specific task.

    Priority:
    1. CLI override (--model flag)
    2. Config file (.egregora/config.yml models.{task})
    3. DEFAULT_MODEL fallback

    Args:
        task: Type of model task (writer, enricher, etc.)
        egregora_config: Optional EgregoraConfig from .egregora/config.yml
        cli_override: Optional CLI model override (--model flag)

    Returns:
        Model name to use

    Examples:
        >>> get_model_for_task("writer", config, cli_model="gemini-2.0-flash")
        "gemini-2.0-flash"  # CLI override
        >>> get_model_for_task("writer", config, None)
        "google-gla:gemini-flash-latest"  # From config
        >>> get_model_for_task("writer", None, None)
        "google-gla:gemini-flash-latest"  # DEFAULT_MODEL

    """
    # CLI override takes precedence
    if cli_override:
        logger.debug("Using CLI model for %s: %s", task, cli_override)
        return cli_override

    # Get from config (defaults already resolved by schema validator)
    if egregora_config:
        model = getattr(egregora_config.models, task)
        logger.debug("Using config model for %s: %s", task, model)
        return model

    # Fallback to DEFAULT_MODEL if no config provided
    logger.debug("Using fallback DEFAULT_MODEL for %s", task)
    return DEFAULT_MODEL


__all__ = [
    # Pydantic config schemas (persisted in .egregora/config.yml)
    "EgregoraConfig",
    "EnrichmentSettings",
    "FeaturesSettings",
    "ModelSettings",
    "OutputSettings",
    "PathsSettings",
    "PipelineSettings",
    "PrivacySettings",
    "RAGSettings",
    "ReaderSettings",
    "WriterAgentSettings",
    # Config loading functions
    "create_default_config",
    "find_egregora_config",
    "load_egregora_config",
    "save_egregora_config",
    # Runtime dataclasses (not persisted, for function parameters)
    "ProcessConfig",
    "WriterRuntimeConfig",
    "MediaEnrichmentContext",
    "EnrichmentRuntimeConfig",
    "PipelineEnrichmentConfig",
    # Model configuration
    "ModelType",
    "get_model_for_task",
    # Constants
    "DEFAULT_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_BANNER_MODEL",
    "EMBEDDING_DIM",
]
