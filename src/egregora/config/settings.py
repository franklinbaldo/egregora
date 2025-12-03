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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from egregora.config.overrides import ConfigOverrideBuilder

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

DEFAULT_MODEL = "google-gla:gemini-2.0-flash"
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
DEFAULT_BANNER_MODEL = "models/gemini-2.5-flash-image"
EMBEDDING_DIM = 768  # Embedding vector dimensions

# Quota defaults
DEFAULT_DAILY_LLM_REQUESTS = 220
DEFAULT_PER_SECOND_LIMIT = 1
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

    # Embedding router settings
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
        """Validate top_k is reasonable."""
        if v > 15:
             # Just return, logging side effects inside validators are discouraged
             # The warning is handled by ConfigValidator if needed
             pass
        return v


class WriterAgentSettings(BaseModel):
    """Blog post writer configuration."""

    custom_instructions: str | None = Field(
        default=None,
        description="Custom instructions to guide the writer agent",
    )


# Import privacy enums early for use in privacy settings classes
from egregora.constants import (  # noqa: E402
    AuthorPrivacyStrategy,
    MentionPrivacyStrategy,
    PIIScope,
    TextPIIStrategy,
)


class AgentPIISettings(BaseModel):
    """PII prevention settings for a specific agent (LLM-native)."""

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
    """LLM-native PII prevention settings for all agents."""

    enricher: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=True,
            scope=PIIScope.CONTACT_INFO,
            apply_to_journals=False,
        ),
        description="Enricher agent PII prevention",
    )

    writer: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=True,
            scope=PIIScope.ALL_PII,
            apply_to_journals=True,
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
    """Structural anonymization settings (adapter-level, deterministic preprocessing)."""

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
    """Privacy and data protection settings (YAML configuration)."""

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


from egregora.constants import WindowUnit  # noqa: E402


class PipelineSettings(BaseModel):
    """Pipeline execution settings."""

    step_size: int = Field(
        default=1,
        ge=1,
        description="Size of each processing window",
    )
    step_unit: WindowUnit = Field(
        default=WindowUnit.DAYS,
        description="Unit for windowing",
    )
    overlap_ratio: float = Field(
        default=0.2,
        ge=0.0,
        le=0.5,
        description="Fraction of window to overlap",
    )
    max_window_time: int | None = Field(
        default=None,
        ge=1,
        description="Maximum time span per window in hours",
    )
    timezone: str | None = Field(
        default=None,
        description="Timezone for timestamp parsing",
    )
    batch_threshold: int = Field(
        default=10,
        ge=1,
        description="Minimum items before batching API calls",
    )
    from_date: str | None = Field(
        default=None,
        description="Start date for filtering",
    )
    to_date: str | None = Field(
        default=None,
        description="End date for filtering",
    )
    max_prompt_tokens: int = Field(
        default=100_000,
        ge=1_000,
        description="Maximum tokens per prompt",
    )
    use_full_context_window: bool = Field(
        default=False,
        description="Use full model context window",
    )
    max_windows: int | None = Field(
        default=1,
        ge=0,
        description="Maximum windows to process per run",
    )
    checkpoint_enabled: bool = Field(
        default=False,
        description="Enable incremental processing with checkpoints",
    )


class PathsSettings(BaseModel):
    """Site directory paths configuration."""

    # .egregora/ internal paths (relative to site_root)
    egregora_dir: str = Field(
        default=".egregora",
        description="Egregora internal directory",
    )
    rag_dir: str = Field(
        default=".egregora/rag",
        description="RAG database and embeddings storage",
    )
    lancedb_dir: str = Field(
        default=".egregora/lancedb",
        description="LanceDB vector database directory",
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
        description="Media files directory",
    )
    journal_dir: str = Field(
        default="journal",
        description="Agent execution journals directory",
    )


class OutputSettings(BaseModel):
    """Output format configuration."""

    format: Literal["mkdocs", "hugo"] = Field(
        default="mkdocs",
        description="Output format",
    )

    mkdocs_config_path: str | None = Field(
        default=None,
        description="Path to mkdocs.yml config file",
    )


class DatabaseSettings(BaseModel):
    """Database configuration for pipeline and observability."""

    pipeline_db: str = Field(
        default=DEFAULT_PIPELINE_DB,
        description="Pipeline database connection URI",
    )
    runs_db: str = Field(
        default=DEFAULT_RUNS_DB,
        description="Run tracking database connection URI",
    )


class ReaderSettings(BaseModel):
    """Reader agent configuration for post evaluation and ranking."""

    enabled: bool = Field(
        default=False,
        description="Enable reader agent",
    )
    comparisons_per_post: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of pairwise comparisons per post",
    )
    k_factor: int = Field(
        default=32,
        ge=16,
        le=64,
        description="ELO K-factor",
    )
    database_path: str = Field(
        default=".egregora/reader.duckdb",
        description="Path to reader database",
    )


class FeaturesSettings(BaseModel):
    """Feature flags for experimental or optional functionality."""

    ranking_enabled: bool = Field(
        default=False,
        description="Enable Elo-based post ranking (deprecated)",
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
        description="Soft limit for daily LLM calls",
    )
    per_second_limit: int = Field(
        default=DEFAULT_PER_SECOND_LIMIT,
        ge=1,
        description="Maximum number of LLM calls allowed per second",
    )
    concurrency: int = Field(
        default=DEFAULT_CONCURRENCY,
        ge=1,
        le=20,
        description="Maximum number of simultaneous LLM tasks",
    )


class EgregoraConfig(BaseModel):
    """Root configuration for Egregora."""

    models: ModelSettings = Field(default_factory=ModelSettings)
    image_generation: ImageGenerationSettings = Field(default_factory=ImageGenerationSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    writer: WriterAgentSettings = Field(default_factory=WriterAgentSettings)
    reader: ReaderSettings = Field(default_factory=ReaderSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    features: FeaturesSettings = Field(default_factory=FeaturesSettings)
    quota: QuotaSettings = Field(default_factory=QuotaSettings)

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    @model_validator(mode="after")
    def validate_cross_field(self) -> EgregoraConfig:
        """Validate cross-field dependencies."""
        # Clean validation without side effects (logging)
        if self.rag.enabled and not self.paths.lancedb_dir:
            msg = (
                "RAG is enabled (rag.enabled=true) but paths.lancedb_dir is not set. "
                "Set paths.lancedb_dir to a valid directory path."
            )
            raise ValueError(msg)
        return self

    @classmethod
    def from_cli_overrides(cls, base_config: EgregoraConfig, **cli_args: Any) -> EgregoraConfig:
        """Create a new config instance with CLI overrides applied."""
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
    """Search upward for .egregora/config.yml."""
    current = start_dir.expanduser().resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / ".egregora" / "config.yml"
        if config_path.exists():
            return config_path
    return None


def load_egregora_config(site_root: Path) -> EgregoraConfig:
    """Load Egregora configuration from .egregora/config.yml."""
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
    except ValidationError as e:
        # Separate validation error logging logic
        _log_validation_errors(config_path, e)
        logger.warning("Creating default config due to validation error")
        return create_default_config(site_root)


def _log_validation_errors(config_path: Path, e: ValidationError) -> None:
    logger.exception("Configuration validation failed for %s:", config_path)
    for error in e.errors():
        loc = " → ".join(str(location_part) for location_part in error["loc"])
        logger.exception("  %s: %s", loc, error["msg"])


def create_default_config(site_root: Path) -> EgregoraConfig:
    """Create default .egregora/config.yml and return it."""
    config = EgregoraConfig()
    save_egregora_config(config, site_root)
    logger.info("Created default config at %s/.egregora/config.yml", site_root)
    return config


def save_egregora_config(config: EgregoraConfig, site_root: Path) -> Path:
    """Save EgregoraConfig to .egregora/config.yml."""
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(exist_ok=True, parents=True)

    config_path = egregora_dir / "config.yml"

    data = config.model_dump(exclude_defaults=False, mode="json")

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


from egregora.constants import WindowUnit  # noqa: E402


@dataclass
class RuntimeContext:
    """Runtime-only context that cannot be persisted to config.yml."""

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
    """Runtime configuration for post writing."""

    posts_dir: Annotated[Path, "Directory to save posts"]
    profiles_dir: Annotated[Path, "Directory to save profiles"]
    rag_dir: Annotated[Path, "Directory for RAG data"]
    model_config: Annotated[object | None, "Model configuration"] = None
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
    """Extended enrichment configuration for pipeline operations."""

    batch_threshold: int = 10
    max_enrichments: int = 500
    enable_url: bool = True
    enable_media: bool = True

    def __post_init__(self) -> None:
        if self.batch_threshold < 1:
            msg = f"batch_threshold must be >= 1, got {self.batch_threshold}"
            raise ValueError(msg)
        if self.max_enrichments < 0:
            msg = f"max_enrichments must be >= 0, got {self.max_enrichments}"
            raise ValueError(msg)

    @classmethod
    def from_cli_args(cls, **kwargs: int | bool) -> PipelineEnrichmentConfig:
        return cls(
            batch_threshold=kwargs.get("batch_threshold", 10),
            max_enrichments=kwargs.get("max_enrichments", 500),
            enable_url=kwargs.get("enable_url", True),
            enable_media=kwargs.get("enable_media", True),
        )


# ============================================================================
# Model Configuration Utilities
# ============================================================================

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


def get_google_api_key() -> str:
    """Get Google API key from environment (checks GOOGLE_API_KEY then GEMINI_API_KEY)."""
    import os

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY (or GEMINI_API_KEY) environment variable is required"
        raise ValueError(msg)
    return api_key


def google_api_key_status() -> bool:
    """Check if GOOGLE_API_KEY or GEMINI_API_KEY is configured."""
    import os

    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


def get_openrouter_api_key() -> str:
    """Get OpenRouter API key from environment."""
    import os

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        msg = "OPENROUTER_API_KEY environment variable is required for OpenRouter models"
        raise ValueError(msg)
    return api_key.strip().lstrip("=").strip()


def openrouter_api_key_status() -> bool:
    """Check if OPENROUTER_API_KEY is configured."""
    import os

    return bool(os.environ.get("OPENROUTER_API_KEY"))
