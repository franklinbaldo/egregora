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
from pathlib import Path
from typing import Annotated, Any, Literal

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
    """Privacy and data protection settings (YAML configuration).

    .. note::
       Currently all privacy features (anonymization, PII detection) are always enabled.
       This config section is reserved for future configurable privacy controls.

    .. warning::
       This Pydantic model (for YAML config) has the same name as the dataclass in
       ``egregora.privacy.config.PrivacySettings`` (for runtime policy). They are NOT
       duplicates - they serve different purposes:

       - **This class**: YAML configuration placeholder (persisted to config.yml)
       - **privacy.config.PrivacySettings**: Runtime policy with tenant isolation, PII
         detection settings, and re-identification escrow (never persisted)

       When privacy configuration becomes user-configurable, this class will hold the
       YAML settings which get mapped to runtime PrivacySettings instances.
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


from egregora.constants import WindowUnit  # noqa: E402


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
        default="media",
        description="Media files (images, videos) directory",
    )
    journal_dir: str = Field(
        default="journal",
        description="Agent execution journals directory",
    )


class OutputSettings(BaseModel):
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


class QuotaSettings(BaseModel):
    """Configuration for LLM usage budgets and concurrency."""

    daily_llm_requests: int = Field(
        default=220,
        ge=1,
        description="Soft limit for daily LLM calls (writer + enrichment).",
    )
    per_second_limit: int = Field(
        default=10,
        ge=1,
        description="Maximum number of LLM calls allowed per second (for async guard).",
    )
    concurrency: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Maximum number of simultaneous LLM tasks (enrichment, writing, etc).",
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
    quota: QuotaSettings = Field(
        default_factory=QuotaSettings,
        description="LLM usage quota tracking",
    )

    model_config = ConfigDict(
        extra="forbid",  # Reject unknown fields
        validate_assignment=True,  # Validate on attribute assignment
    )

    @classmethod
    def from_cli_overrides(cls, base_config: EgregoraConfig, **cli_args: Any) -> EgregoraConfig:  # noqa: C901, PLR0912
        """Create a new config instance with CLI overrides applied.

        Handles nested updates for pipeline, enrichment, rag, etc.
        CLI arguments are expected to be flat key-value pairs or dicts
        matching the argument structure of CLI commands.
        """
        # Create dict representation for updates
        updates = base_config.model_dump()

        # Pipeline overrides
        if "step_size" in cli_args and cli_args["step_size"] is not None:
            updates["pipeline"]["step_size"] = cli_args["step_size"]
        if "step_unit" in cli_args and cli_args["step_unit"] is not None:
            updates["pipeline"]["step_unit"] = cli_args["step_unit"]
        if "overlap_ratio" in cli_args and cli_args["overlap_ratio"] is not None:
            updates["pipeline"]["overlap_ratio"] = cli_args["overlap_ratio"]
        if "timezone" in cli_args and cli_args["timezone"] is not None:
            updates["pipeline"]["timezone"] = str(cli_args["timezone"])
        if "from_date" in cli_args and cli_args["from_date"] is not None:
            updates["pipeline"]["from_date"] = cli_args["from_date"].isoformat()
        if "to_date" in cli_args and cli_args["to_date"] is not None:
            updates["pipeline"]["to_date"] = cli_args["to_date"].isoformat()
        if "max_prompt_tokens" in cli_args and cli_args["max_prompt_tokens"] is not None:
            updates["pipeline"]["max_prompt_tokens"] = cli_args["max_prompt_tokens"]
        if "use_full_context_window" in cli_args and cli_args["use_full_context_window"] is not None:
            updates["pipeline"]["use_full_context_window"] = cli_args["use_full_context_window"]

        # Enrichment overrides
        if "enable_enrichment" in cli_args:
            updates["enrichment"]["enabled"] = cli_args["enable_enrichment"]

        # RAG overrides
        if "retrieval_mode" in cli_args and cli_args["retrieval_mode"] is not None:
            updates["rag"]["mode"] = cli_args["retrieval_mode"]
        if "retrieval_nprobe" in cli_args and cli_args["retrieval_nprobe"] is not None:
            updates["rag"]["nprobe"] = cli_args["retrieval_nprobe"]
        if "retrieval_overfetch" in cli_args and cli_args["retrieval_overfetch"] is not None:
            updates["rag"]["overfetch"] = cli_args["retrieval_overfetch"]

        # Model overrides (apply single CLI model arg to all relevant models)
        if cli_args.get("model"):
            model = cli_args["model"]
            updates["models"]["writer"] = model
            updates["models"]["enricher"] = model
            updates["models"]["enricher_vision"] = model
            updates["models"]["ranking"] = model
            updates["models"]["editor"] = model

        return cls.model_validate(updates)


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
    except OSError:
        logger.exception("Failed to read config from %s", config_path)
        raise

    try:
        data = yaml.safe_load(raw_config) or {}
    except yaml.YAMLError:
        logger.exception("Failed to parse YAML in %s", config_path)
        raise

    try:
        return EgregoraConfig(**data)
    except ValidationError:
        logger.exception("Validation failed for %s", config_path)
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


from egregora.constants import WindowUnit  # noqa: E402


@dataclass
class RuntimeContext:
    """Runtime-only context that cannot be persisted to config.yml.

    This is the minimal set of fields that are truly runtime-specific:
    - Paths resolved at invocation time
    - API keys from environment
    - Debug flags

    All other configuration lives in EgregoraConfig (single source of truth).
    """

    output_dir: Annotated[Path, "Directory for the generated site"]
    input_file: Annotated[Path | None, "Path to the chat export file"] = None
    api_key: Annotated[str | None, "Google API key (from env or CLI)"] = None
    model_override: Annotated[str | None, "Model override from CLI"] = None
    debug: Annotated[bool, "Enable debug logging"] = False

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


__all__ = [
    "DEFAULT_BANNER_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_MODEL",
    "EMBEDDING_DIM",
    "EgregoraConfig",
    "EnrichmentRuntimeConfig",
    "EnrichmentSettings",
    "FeaturesSettings",
    "MediaEnrichmentContext",
    "ModelSettings",
    "ModelType",
    "OutputSettings",
    "PathsSettings",
    "PipelineEnrichmentConfig",
    "PipelineSettings",
    "PrivacySettings",
    "RAGSettings",
    "ReaderSettings",
    "RuntimeContext",
    "WriterAgentSettings",
    "WriterRuntimeConfig",
    "create_default_config",
    "find_egregora_config",
    "load_egregora_config",
    "save_egregora_config",
]
