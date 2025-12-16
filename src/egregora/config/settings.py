"""Centralized configuration for Egregora (ALPHA VERSION).

This module consolidates ALL configuration code in one place:
- Pydantic models for .egregora/egregora.toml
- Loading and saving functions
- Runtime dataclasses for function parameters
- Model configuration utilities

Benefits:
- Single source of truth for all configuration
- Backend independence (works with Hugo, Astro, etc.)
- Type safety (Pydantic validation at load time)
- No backward compatibility - clean alpha design

Strategy:
- ONLY loads from .egregora/egregora.toml
- Creates default config if missing
- No mkdocs.yml fallback
- No legacy transformation
"""

from __future__ import annotations

import logging
import os
import tomllib  # Requires Python 3.11+
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

import tomli_w
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from egregora.constants import WindowUnit

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

DEFAULT_MODEL = "google-gla:gemini-flash-latest"  # More reliable availability
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
DEFAULT_BANNER_MODEL = "models/gemini-2.5-flash-image"
EMBEDDING_DIM = 768  # Embedding vector dimensions

# Quota defaults
DEFAULT_DAILY_LLM_REQUESTS = 100  # Conservative default
DEFAULT_PER_SECOND_LIMIT = 0.05  # ~3 requests/min to avoid 429 on free tier
DEFAULT_CONCURRENCY = 1

# Default database connection strings
DEFAULT_PIPELINE_DB = "duckdb:///./.egregora/pipeline.duckdb"
DEFAULT_RUNS_DB = "duckdb:///./.egregora/runs.duckdb"

# Configuration validation warning thresholds
RAG_TOP_K_WARNING_THRESHOLD = 20
MAX_PROMPT_TOKENS_WARNING_THRESHOLD = 200_000

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
    reader: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for reader agent (pydantic-ai format)",
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

    @field_validator("writer", "enricher", "enricher_vision", "ranking", "editor", "reader")
    @classmethod
    def validate_pydantic_model_format(cls, v: str) -> str:
        """Validate Pydantic-AI model name format."""
        if not v.startswith("google-gla:"):
            msg = (
                f"Invalid Pydantic-AI model format: {v!r}\n"
                f"Expected format: 'google-gla:<model-name>'\n"
                f"Examples:\n"
                f"  - google-gla:gemini-flash-latest\n"
                f"  - google-gla:gemini-2.0-flash-exp\n"
                f"  - google-gla:gemini-1.5-pro"
            )
            raise ValueError(msg)
        return v

    @field_validator("embedding", "banner")
    @classmethod
    def validate_google_model_format(cls, v: str) -> str:
        """Validate Google GenAI SDK model name format."""
        if not v.startswith("models/"):
            msg = (
                f"Invalid Google GenAI model format: {v!r}\n"
                f"Expected format: 'models/<model-name>'\n"
                f"Examples:\n"
                f"  - models/gemini-embedding-001\n"
                f"  - models/gemini-2.5-flash-image"
            )
            raise ValueError(msg)
        return v


class ImageGenerationSettings(BaseModel):
    """Configuration for image generation requests."""

    response_modalities: list[str] = Field(
        default_factory=lambda: ["IMAGE", "TEXT"],
        description="Modalities requested from image generation APIs",
    )
    aspect_ratio: str = Field(
        default="16:9",
        description="Aspect ratio hint for generated banner images",
    )


class RAGSettings(BaseModel):
    """Retrieval-Augmented Generation (RAG) configuration.

    Uses LanceDB for vector storage and similarity search.
    Embedding API uses dual-queue router for optimal throughput.
    """

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
    indexable_types: list[str] = Field(
        default=["POST"],
        description="Document types to index in RAG (e.g., ['POST', 'NOTE'])",
    )

    # Embedding router settings (dual-queue architecture)
    embedding_max_batch_size: int = Field(
        default=100,
        ge=1,
        le=100,
        description="Maximum texts per batch embedding request (Google API limit: 100)",
    )
    embedding_timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=600.0,
        description="HTTP timeout for embedding requests in seconds",
    )
    embedding_max_retries: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum consecutive errors before failing (per endpoint)",
    )

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """Validate top_k is reasonable and warn if too high."""
        if v > RAG_TOP_K_WARNING_THRESHOLD:
            logger.warning(
                "RAG top_k=%s is unusually high. "
                "Consider values between 5-10 for better performance and relevance.",
                v,
            )
        return v


class WriterAgentSettings(BaseModel):
    """Blog post writer configuration."""

    custom_instructions: str | None = Field(
        default=None,
        description="Custom instructions to guide the writer agent",
    )
    economic_system_instruction: str | None = Field(
        default=None,
        description="Override system instruction for economic mode writer",
    )
    economic_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Temperature for economic mode generation (0.0=deterministic, 1.0=creative)",
    )


class PrivacySettings(BaseModel):
    """Privacy and PII configuration."""

    anonymization_enabled: bool = Field(
        default=True,
        description="Enable author name anonymization",
    )
    pii_detection_enabled: bool = Field(
        default=True,
        description="Enable PII detection and redaction in content",
    )
    scrub_emails: bool = Field(
        default=True,
        description="Scrub email addresses",
    )
    scrub_phones: bool = Field(
        default=True,
        description="Scrub phone numbers",
    )


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
    strategy: Literal["individual", "batch_api", "batch_all"] = Field(
        default="batch_all",
        description="Enrichment strategy: individual (1 call per item), batch_api (Gemini batch), batch_all (all in one call)",
    )
    model_rotation_enabled: bool = Field(
        default=True,
        description="Rotate through Gemini models on 429 errors",
    )
    rotation_models: list[str] = Field(
        default=[
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.5-pro",
        ],
        description="List of Gemini models to rotate through on rate limits",
    )
    max_enrichments: int = Field(
        default=50,
        ge=0,
        le=200,
        description="Maximum number of enrichments per run",
    )
    max_concurrent_enrichments: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description=(
            "Maximum concurrent enrichment requests. "
            "None (default) enables auto-scaling based on available API keys. "
            "Set to 1 to explicitly disable auto-scaling and use sequential processing."
        ),
    )


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
    economic_mode: bool = Field(
        default=False,
        description="Enable economic mode to reduce LLM costs (2 calls per window, no tool usage).",
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
        description="RAG database and embeddings storage (DuckDB backend)",
    )
    lancedb_dir: str = Field(
        default=".egregora/lancedb",
        description="LanceDB vector database directory (LanceDB backend)",
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

    @field_validator(
        "egregora_dir",
        "rag_dir",
        "lancedb_dir",
        "cache_dir",
        "prompts_dir",
        "docs_dir",
        "posts_dir",
        "profiles_dir",
        "media_dir",
        "journal_dir",
        mode="after",
    )
    @classmethod
    def validate_safe_path(cls, v: str) -> str:
        """Validate path is relative and does not contain traversal sequences."""
        if not v:
            return v
        path = Path(v)
        if path.is_absolute():
            msg = f"Path must be relative, not absolute: {v}"
            raise ValueError(msg)
        if any(part == ".." for part in path.parts):
            msg = f"Path must not contain traversal sequences ('..'): {v}"
            raise ValueError(msg)
        return v


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
        default=DEFAULT_PIPELINE_DB,
        description=(
            "Pipeline database connection URI (e.g. 'duckdb:///absolute/path.duckdb', "
            "'duckdb:///./.egregora/pipeline.duckdb' for a site-relative file, or "
            "'postgres://user:pass@host:5432/dbname')."
        ),
    )
    runs_db: str = Field(
        default=DEFAULT_RUNS_DB,
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
        default=DEFAULT_DAILY_LLM_REQUESTS,
        ge=1,
        description="Soft limit for daily LLM calls (writer + enrichment).",
    )
    per_second_limit: float = Field(
        default=DEFAULT_PER_SECOND_LIMIT,
        ge=0.01,
        description="Maximum number of LLM calls allowed per second (for async guard).",
    )
    concurrency: int = Field(
        default=DEFAULT_CONCURRENCY,
        ge=1,
        le=20,
        description="Maximum number of simultaneous LLM tasks (enrichment, writing, etc).",
    )


class EgregoraConfig(BaseSettings):
    """Root configuration for Egregora.

    This model defines the complete .egregora/egregora.toml schema.

    Supports environment variable overrides with the pattern:
    EGREGORA_SECTION__KEY (e.g., EGREGORA_MODELS__WRITER)
    """

    models: ModelSettings = Field(
        default_factory=ModelSettings,
        description="LLM model configuration",
    )
    image_generation: ImageGenerationSettings = Field(
        default_factory=ImageGenerationSettings,
        description="Image generation request settings",
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

    model_config = SettingsConfigDict(
        extra="forbid",  # Reject unknown fields
        validate_assignment=True,  # Validate on attribute assignment
        env_prefix="EGREGORA_",
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def validate_cross_field(self) -> EgregoraConfig:
        """Validate cross-field dependencies and warn about potential issues."""
        # If RAG is enabled, ensure lancedb_dir is set
        if self.rag.enabled and not self.paths.lancedb_dir:
            msg = (
                "RAG is enabled (rag.enabled=true) but paths.lancedb_dir is not set. "
                "Set paths.lancedb_dir to a valid directory path."
            )
            raise ValueError(msg)

        # Warn about very high max_prompt_tokens
        if self.pipeline.max_prompt_tokens > MAX_PROMPT_TOKENS_WARNING_THRESHOLD:
            logger.warning(
                "pipeline.max_prompt_tokens=%s exceeds most model limits. "
                "Consider using pipeline.use_full_context_window=true instead of setting a high token limit.",
                self.pipeline.max_prompt_tokens,
            )

        # Warn if use_full_context_window is enabled
        if self.pipeline.use_full_context_window:
            logger.info(
                "pipeline.use_full_context_window=true. Using full model context window "
                "(overrides max_prompt_tokens setting)."
            )

        # Check for deprecated feature flags
        if self.features.ranking_enabled:
            logger.warning("features.ranking_enabled is deprecated. Use reader.enabled instead.")

        return self

    @classmethod
    def from_cli_overrides(cls, base_config: EgregoraConfig, **cli_args: Any) -> EgregoraConfig:
        """Create a new config instance with CLI overrides applied.

        Handles nested updates for pipeline, enrichment, rag, etc.
        CLI arguments are expected to be flat key-value pairs or dicts
        matching the argument structure of CLI commands.
        """
        # Apply pipeline settings overrides
        pipeline_overrides = {}
        for key in [
            "step_size",
            "step_unit",
            "overlap_ratio",
            "max_prompt_tokens",
            "use_full_context_window",
        ]:
            if key in cli_args and cli_args[key] is not None:
                pipeline_overrides[key] = cli_args[key]

        if cli_args.get("timezone") is not None:
            pipeline_overrides["timezone"] = str(cli_args["timezone"])

        from_date = cli_args.get("from_date")
        if from_date:
            pipeline_overrides["from_date"] = from_date.isoformat()

        to_date = cli_args.get("to_date")
        if to_date:
            pipeline_overrides["to_date"] = to_date.isoformat()

        # Apply enrichment settings overrides
        enrichment_overrides = {}
        if "enable_enrichment" in cli_args and cli_args["enable_enrichment"] is not None:
            enrichment_overrides["enabled"] = cli_args["enable_enrichment"]

        # Apply rag settings overrides
        rag_overrides = {}
        # NOTE: retrieval_mode/nprobe/overfetch removed from CLI args as per V3 simplification

        # Apply model overrides
        model_overrides = {}
        if cli_args.get("model"):
            model = cli_args["model"]
            model_overrides = {
                "writer": model,
                "enricher": model,
                "enricher_vision": model,
                "ranking": model,
                "editor": model,
            }

        # Construct updates
        updates = {}
        if pipeline_overrides:
            updates["pipeline"] = base_config.pipeline.model_copy(update=pipeline_overrides)
        if enrichment_overrides:
            updates["enrichment"] = base_config.enrichment.model_copy(update=enrichment_overrides)
        if rag_overrides:
            updates["rag"] = base_config.rag.model_copy(update=rag_overrides)
        if model_overrides:
            updates["models"] = base_config.models.model_copy(update=model_overrides)

        return base_config.model_copy(update=updates)


# ============================================================================
# Configuration Loading and Saving
# ============================================================================


def find_egregora_config(start_dir: Path) -> Path | None:
    """Search upward for .egregora/egregora.toml (or config.yml as fallback).

    Args:
        start_dir: Starting directory for upward search

    Returns:
        Path to config file if found, else None

    """
    current = start_dir.expanduser().resolve()
    for candidate in (current, *current.parents):
        # Prefer TOML
        toml_path = candidate / ".egregora" / "egregora.toml"
        if toml_path.exists():
            return toml_path

        # Fallback to YAML (but warn/deprecate? For now just support finding it)
        yaml_path = candidate / ".egregora" / "config.yml"
        if yaml_path.exists():
            return yaml_path

    return None


def _collect_env_override_paths() -> set[tuple[str, ...]]:
    """Return the set of config paths defined via environment variables."""
    prefix = "EGREGORA_"
    env_paths: set[tuple[str, ...]] = set()

    for key in os.environ:
        if not key.startswith(prefix):
            continue
        parts = [part.lower() for part in key[len(prefix) :].split("__") if part]
        if parts:
            env_paths.add(tuple(parts))

    return env_paths


def _merge_config(
    base: dict[str, Any],
    override: dict[str, Any],
    env_override_paths: set[tuple[str, ...]],
    current_path: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Merge override into base, skipping keys provided via env vars."""
    merged = deepcopy(base)

    for key, value in override.items():
        path = (*current_path, str(key).lower())
        if path in env_override_paths:
            continue

        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value, env_override_paths, path)
        else:
            merged[key] = value

    return merged


def load_egregora_config(site_root: Path | None = None) -> EgregoraConfig:
    """Load Egregora configuration from .egregora/egregora.toml.

    Configuration priority (highest to lowest):
    1. CLI (applied via from_cli_overrides later)
    2. Environment variables (EGREGORA_SECTION__KEY)
    3. Config file (.egregora/egregora.toml)
    4. Defaults

    Args:
        site_root: Root directory of the site. If None, uses current working directory.

    Returns:
        Validated EgregoraConfig instance

    Raises:
        ValidationError: If config file contains invalid data

    """
    if site_root is None:
        site_root = Path.cwd()

    config_path = find_egregora_config(site_root)

    if not config_path:
        # Check standard location if find failed
        config_path = site_root / ".egregora" / "egregora.toml"

    if not config_path.exists():
        logger.info("No configuration found, creating default config at %s", config_path)
        return create_default_config(site_root)

    logger.info("Loading config from %s", config_path)

    try:
        raw_config = config_path.read_text(encoding="utf-8")
    except OSError:
        logger.exception("Failed to read config from %s", config_path)
        raise

    try:
        if config_path.suffix == ".toml":
            file_data = tomllib.loads(raw_config)
        else:
            # Fallback for YAML
            import yaml

            file_data = yaml.safe_load(raw_config) or {}
    except (ValueError, ImportError) as e:
        logger.exception("Failed to parse config in %s: %s", config_path, e)
        raise

    try:
        # Create base config with defaults
        base_config = EgregoraConfig()
        base_dict = base_config.model_dump(mode="json")

        # Merge file config into base, skipping keys that are set in env vars
        # This logic preserves: Env Vars > Config File > Defaults
        env_override_paths = _collect_env_override_paths()
        merged = _merge_config(base_dict, file_data, env_override_paths)

        # Validate and return
        return EgregoraConfig.model_validate(merged)
    except ValidationError as e:
        logger.exception("Configuration validation failed for %s:", config_path)
        for error in e.errors():
            loc = " -> ".join(str(location_part) for location_part in error["loc"])
            logger.exception("  %s: %s", loc, error["msg"])
        logger.warning("Creating default config due to validation error")
        return create_default_config(site_root)


def create_default_config(site_root: Path) -> EgregoraConfig:
    """Create default .egregora/egregora.toml and return it.

    Args:
        site_root: Root directory of the site

    Returns:
        EgregoraConfig with all defaults

    """
    config = EgregoraConfig()  # All defaults from Pydantic
    save_egregora_config(config, site_root)
    logger.info("Created default config at %s/.egregora/egregora.toml", site_root)
    return config


def save_egregora_config(config: EgregoraConfig, site_root: Path) -> Path:
    """Save EgregoraConfig to .egregora/egregora.toml.

    Creates .egregora/ directory if it doesn't exist.

    Args:
        config: EgregoraConfig instance to save
        site_root: Root directory of the site

    Returns:
        Path to the saved config file

    """
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(exist_ok=True, parents=True)

    config_path = egregora_dir / "egregora.toml"

    # Export as dict
    data = config.model_dump(exclude_defaults=False, mode="json")

    # Remove None values as tomli_w doesn't support them
    def _clean_nones(d: dict[str, Any]) -> dict[str, Any]:
        cleaned = {}
        for k, v in d.items():
            if v is None:
                continue
            if isinstance(v, dict):
                v = _clean_nones(v)
            cleaned[k] = v
        return cleaned

    data = _clean_nones(data)

    # Write as TOML
    toml_str = tomli_w.dumps(data)

    config_path.write_text(toml_str, encoding="utf-8")
    logger.debug("Saved config to %s", config_path)

    return config_path


# ============================================================================
# Validation Utilities (Consolidated from config_validation.py)
# ============================================================================


def parse_date_arg(date_str: str, arg_name: str = "date") -> date:
    """Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string in YYYY-MM-DD format
        arg_name: Name of the argument (for error messages)

    Returns:
        date object in UTC

    Raises:
        ValueError: If date_str is not in YYYY-MM-DD format

    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC).date()
    except ValueError as e:
        msg = f"Invalid {arg_name} format: {e}. Expected format: YYYY-MM-DD"
        raise ValueError(msg) from e


def validate_timezone(timezone_str: str) -> ZoneInfo:
    """Validate timezone string and return ZoneInfo object.

    Args:
        timezone_str: Timezone identifier (e.g., 'America/New_York', 'UTC')

    Returns:
        ZoneInfo object for the specified timezone

    Raises:
        ValueError: If timezone_str is not a valid timezone identifier

    """
    try:
        return ZoneInfo(timezone_str)
    except Exception as e:
        msg = f"Invalid timezone '{timezone_str}': {e}"
        raise ValueError(msg) from e


def validate_retrieval_config(
    retrieval_mode: str,
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> str:
    """Validate and normalize retrieval mode configuration.

    (Kept for compatibility with any remaining callers, though params are deprecated)
    """
    normalized_mode = (retrieval_mode or "ann").lower()
    if normalized_mode not in {"ann", "exact"}:
        msg = "Invalid retrieval mode. Choose 'ann' or 'exact'."
        raise ValueError(msg)

    if retrieval_nprobe is not None and retrieval_nprobe <= 0:
        raise ValueError("retrieval_nprobe must be positive")

    if retrieval_overfetch is not None and retrieval_overfetch <= 0:
        raise ValueError("retrieval_overfetch must be positive")

    return normalized_mode


# ============================================================================
# Runtime Configuration Dataclasses
# ============================================================================
# These dataclasses are used for function parameters (not persisted to YAML/TOML).


@dataclass
class RuntimeContext:
    """Runtime-only context that cannot be persisted to config file.

    This is the minimal set of fields that are truly runtime-specific:
    - Paths resolved at invocation time
    - Debug flags

    API keys are read directly from environment variables by pydantic-ai/genai.
    All other configuration lives in EgregoraConfig (single source of truth).
    """

    output_dir: Annotated[Path, "Directory for the generated site"]
    input_file: Annotated[Path | None, "Path to the chat export file"] = None
    model_override: Annotated[str | None, "Model override from CLI"] = None
    debug: Annotated[bool, "Enable debug logging"] = False

    @property
    def input_path(self) -> Path | None:
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
    def from_cli_args(cls, **kwargs: Any) -> PipelineEnrichmentConfig:
        """Create config from CLI arguments."""
        return cls(
            batch_threshold=int(kwargs.get("batch_threshold", 10)),
            max_enrichments=int(kwargs.get("max_enrichments", 500)),
            enable_url=bool(kwargs.get("enable_url", True)),
            enable_media=bool(kwargs.get("enable_media", True)),
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
    "DEFAULT_PIPELINE_DB",
    "DEFAULT_RUNS_DB",
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
    "parse_date_arg",
    "save_egregora_config",
    "validate_retrieval_config",
    "validate_timezone",
]


def get_openrouter_api_key() -> str:
    """Get OpenRouter API key from environment."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        msg = "OPENROUTER_API_KEY environment variable is required for OpenRouter models"
        raise ValueError(msg)
    # Handle bash export syntax (e.g., "= value" instead of "value")
    return api_key.strip().lstrip("=").strip()


def openrouter_api_key_status() -> bool:
    """Check if OPENROUTER_API_KEY is configured."""
    return bool(os.environ.get("OPENROUTER_API_KEY"))
