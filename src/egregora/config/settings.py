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
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from egregora.config.overrides import ConfigOverrideBuilder
from egregora.constants import (
    AuthorPrivacyStrategy,
    MentionPrivacyStrategy,
    PIIScope,
    TextPIIStrategy,
    WindowUnit,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

DEFAULT_MODEL = "google-gla:gemini-flash-latest"  # More reliable availability
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
DEFAULT_BANNER_MODEL = "models/gemini-2.5-flash-image"
EMBEDDING_DIM = 768  # Embedding vector dimensions

# Quota defaults
# Quota defaults
DEFAULT_DAILY_LLM_REQUESTS = 100  # Conservative default
DEFAULT_PER_SECOND_LIMIT = 0.05  # ~3 requests/min to avoid 429 on free tier
DEFAULT_CONCURRENCY = 1

# Default database connection strings
# Can be overridden via config.yml or environment variables
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


class AgentPIISettings(BaseModel):
    """PII prevention settings for a specific agent (LLM-native).

    LLMs naturally understand what constitutes PII without regex patterns.
    We just tell them what we consider private using declarative scopes.
    """

    enabled: bool = Field(
        default=True,
        description="Enable PII prevention for this agent",
    )

    scope: PIIScope = Field(
        default=PIIScope.CONTACT_INFO,
        description="What PII to protect (LLM understands these categories natively)",
    )

    custom_definition: str | None = Field(
        default=None,
        description="Custom PII definition (when scope=custom). LLM will interpret this.",
    )

    apply_to_journals: bool = Field(
        default=True,
        description="Also protect agent execution journals (not just main output)",
    )


class PIIPreventionSettings(BaseModel):
    """LLM-native PII prevention settings for all agents.

    No regex patterns needed - LLMs naturally understand PII.
    """

    enricher: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=True,
            scope=PIIScope.CONTACT_INFO,
            apply_to_journals=False,  # Enricher journals typically internal
        ),
        description="Enricher agent PII prevention",
    )

    writer: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=True,
            scope=PIIScope.ALL_PII,
            apply_to_journals=True,  # CRITICAL: protect journals too
        ),
        description="Writer agent PII prevention",
    )

    banner: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=False,
            scope=PIIScope.CONTACT_INFO,
            apply_to_journals=False,
        ),
        description="Banner agent PII prevention (image generation)",
    )

    reader: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=False,
            scope=PIIScope.CONTACT_INFO,
            apply_to_journals=False,
        ),
        description="Reader agent PII prevention (typically disabled)",
    )


class StructuralPrivacySettings(BaseModel):
    """Structural anonymization settings (adapter-level, deterministic preprocessing).

    Uses simple regex patterns for deterministic preprocessing of raw input data.
    This is separate from LLM-native PII prevention which uses natural language.
    """

    enabled: bool = Field(
        default=True,
        description="Enable structural anonymization",
    )

    author_strategy: AuthorPrivacyStrategy = Field(
        default=AuthorPrivacyStrategy.UUID_MAPPING,
        description="Author anonymization strategy",
    )

    mention_strategy: MentionPrivacyStrategy = Field(
        default=MentionPrivacyStrategy.UUID_REPLACEMENT,
        description="Mention handling strategy",
    )

    phone_strategy: TextPIIStrategy = Field(
        default=TextPIIStrategy.REDACT,
        description="Phone number handling in raw text",
    )

    email_strategy: TextPIIStrategy = Field(
        default=TextPIIStrategy.REDACT,
        description="Email handling in raw text",
    )


class PrivacySettings(BaseModel):
    """Privacy and data protection settings (YAML configuration).

    Two-level privacy model:
    1. **Structural** (Level 1): Deterministic preprocessing of raw input data
    2. **PII Prevention** (Level 2): LLM-native PII understanding in agent outputs

    .. warning::
       Disabling privacy features should only be done for public datasets
       (e.g., judicial records, public archives, news articles).

       For private conversations, always keep privacy enabled to protect PII.

    This Pydantic model (for YAML config) has the same name as the dataclass in
    ``egregora.privacy.config.PrivacySettings`` (for runtime policy). They serve
    different purposes:

    - **This class**: YAML configuration (persisted to config.yml)
    - **privacy.config.PrivacySettings**: Runtime policy with tenant isolation
    """

    structural: StructuralPrivacySettings = Field(
        default_factory=StructuralPrivacySettings,
        description="Structural anonymization settings (adapter-level)",
    )

    pii_prevention: PIIPreventionSettings = Field(
        default_factory=PIIPreventionSettings,
        description="PII prevention in LLM outputs (per-agent, LLM-native)",
    )

    # Backward compatibility properties
    @property
    def enabled(self) -> bool:
        """Legacy: overall privacy enabled (checks structural privacy)."""
        return self.structural.enabled

    @property
    def anonymize_authors(self) -> bool:
        """Legacy: check if authors are being anonymized."""
        return self.structural.author_strategy != AuthorPrivacyStrategy.NONE

    @model_validator(mode="after")
    def validate_privacy_settings(self) -> PrivacySettings:
        """Validate privacy settings and warn if disabled."""
        if not self.structural.enabled:
            logger.warning(
                "⚠️  Structural privacy is DISABLED (privacy.structural.enabled=false). "
                "Only use for public datasets! Private conversations will NOT be anonymized."
            )

        if self.structural.author_strategy == AuthorPrivacyStrategy.NONE and self.structural.enabled:
            logger.warning(
                "Author anonymization is disabled (strategy=none) but structural privacy is enabled. "
                "Author names will appear in output."
            )

        # Warn about journal protection
        if self.pii_prevention.writer.enabled and not self.pii_prevention.writer.apply_to_journals:
            logger.warning(
                "Writer PII prevention is enabled but apply_to_journals=false. "
                "Agent execution journals may contain PII!"
            )

        return self


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
    max_concurrent_enrichments: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent enrichment requests to prevent rate limiting",
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

    This model defines the complete .egregora/config.yml schema.

    Supports environment variable overrides with the pattern:
    EGREGORA_SECTION__KEY (e.g., EGREGORA_MODELS__WRITER)

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
        builder = ConfigOverrideBuilder(base_config)

        builder.with_pipeline(
            step_size=cli_args.get("step_size"),
            step_unit=cli_args.get("step_unit"),
            overlap_ratio=cli_args.get("overlap_ratio"),
            timezone=str(cli_args["timezone"]) if cli_args.get("timezone") is not None else None,
            from_date=cli_args.get("from_date").isoformat() if cli_args.get("from_date") else None,
            to_date=cli_args.get("to_date").isoformat() if cli_args.get("to_date") else None,
            max_prompt_tokens=cli_args.get("max_prompt_tokens"),
            use_full_context_window=cli_args.get("use_full_context_window"),
        )

        builder.with_enrichment(
            enabled=cli_args.get("enable_enrichment") if "enable_enrichment" in cli_args else None
        )

        builder.with_rag(
            mode=cli_args.get("retrieval_mode"),
            nprobe=cli_args.get("retrieval_nprobe"),
            overfetch=cli_args.get("retrieval_overfetch"),
        )

        builder.with_models(model=cli_args.get("model"))

        return builder.build()


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
    """Load Egregora configuration from .egregora/config.yml.

    Configuration priority (highest to lowest):
    1. Environment variables (EGREGORA_SECTION__KEY)
    2. Config file (.egregora/config.yml)
    3. Defaults

    Args:
        site_root: Root directory of the site. If None, uses current working directory.

    Returns:
        Validated EgregoraConfig instance

    Raises:
        ValidationError: If config file contains invalid data

    Examples:
        # Use current working directory
        config = load_egregora_config()

        # Use explicit path (e.g., from CLI --site-root flag)
        config = load_egregora_config(Path("/path/to/site"))

    """
    if site_root is None:
        site_root = Path.cwd()

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
        file_data = yaml.safe_load(raw_config) or {}
    except yaml.YAMLError:
        logger.exception("Failed to parse YAML in %s", config_path)
        raise

    try:
        # Create base config with defaults and environment variables
        base_config = EgregoraConfig()
        base_dict = base_config.model_dump(mode="json")

        # Merge file config into base, skipping env var overrides
        env_override_paths = _collect_env_override_paths()
        merged = _merge_config(base_dict, file_data, env_override_paths)

        # Validate and return
        return EgregoraConfig.model_validate(merged)
    except ValidationError as e:
        logger.exception("Configuration validation failed for %s:", config_path)
        for error in e.errors():
            loc = " → ".join(str(location_part) for location_part in error["loc"])
            logger.exception("  %s: %s", loc, error["msg"])
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


@dataclass
class RuntimeContext:
    """Runtime-only context that cannot be persisted to config.yml.

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
    "save_egregora_config",
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
