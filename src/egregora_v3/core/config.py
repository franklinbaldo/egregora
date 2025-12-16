"""Centralized configuration for Egregora V3.

This module consolidates ALL configuration code in one place:
- Pydantic models for .egregora/config.yml
- Loading and saving functions
- Runtime dataclasses for function parameters
- Model configuration utilities

Benefits:
- Single source of truth for all configuration
- Backend independence (works with Hugo, Astro, etc.)
- Type safety (Pydantic validation at load time)
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

from egregora_v3.core.config_overrides import ConfigOverrideBuilder
from egregora_v3.core.types import WindowUnit

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
    """LLM model configuration for different tasks."""

    # Text generation agents
    writer: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for blog post generation",
    )
    enricher: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for URL/text enrichment",
    )
    enricher_vision: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for image/video enrichment",
    )
    ranking: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for post ranking",
    )
    editor: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for interactive post editing",
    )
    reader: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model for reader agent",
    )

    # Special models with their own defaults
    embedding: GoogleModelName = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="Model for vector embeddings (models/gemini-embedding-001)",
    )
    banner: GoogleModelName = Field(
        default=DEFAULT_BANNER_MODEL,
        description="Model for banner/cover image generation",
    )

    # V3 Fallback support
    fallback_enabled: bool = Field(default=True, description="Enable fallback to secondary provider")
    fallback_model: str = Field(default="openrouter:google/gemini-flash-1.5", description="Fallback model ID")

    @field_validator("writer", "enricher", "enricher_vision", "ranking", "editor", "reader")
    @classmethod
    def validate_pydantic_model_format(cls, v: str) -> str:
        """Validate Pydantic-AI model name format."""
        if not v.startswith("google-gla:"):
            if v.startswith("openrouter:"): # Allow openrouter too
                return v
            msg = f"Invalid Pydantic-AI model format: {v}. Expected 'google-gla:' prefix."
            raise ValueError(msg)
        return v

    @field_validator("embedding", "banner")
    @classmethod
    def validate_google_model_format(cls, v: str) -> str:
        """Validate Google GenAI SDK model name format."""
        if not v.startswith("models/"):
            msg = f"Invalid Google GenAI model format: {v}. Expected 'models/' prefix."
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
    indexable_types: list[str] = Field(
        default=["POST"],
        description="Document types to index in RAG",
    )

    # Embedding router settings
    embedding_max_batch_size: int = Field(
        default=100,
        ge=1,
        le=100,
        description="Maximum texts per batch embedding request",
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
        description="Maximum consecutive errors before failing",
    )


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
        description="Temperature for economic mode generation",
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
        description="Enrichment strategy",
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
    max_concurrent_enrichments: int = Field(
        default=1,
        ge=1,
        le=20,
        description="Maximum concurrent enrichment requests",
    )


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
    economic_mode: bool = Field(
        default=False,
        description="Enable economic mode",
    )


class PathsSettings(BaseModel):
    """Site directory paths configuration."""

    # .egregora/ internal paths
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

    # Content paths
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

    # V3 compatibility additions
    site_root: Path = Field(default_factory=Path.cwd, exclude=True)  # Runtime only, defaults to CWD

    @property
    def abs_posts_dir(self) -> Path:
        return self._resolve(self.posts_dir)

    @property
    def abs_profiles_dir(self) -> Path:
        return self._resolve(self.profiles_dir)

    @property
    def abs_media_dir(self) -> Path:
        return self._resolve(self.media_dir)

    @property
    def abs_lancedb_path(self) -> Path:
        return self._resolve(self.lancedb_dir)

    def _resolve(self, path_str: str) -> Path:
        path = Path(path_str)
        if path.is_absolute():
            return path
        return self.site_root / path

    @field_validator(
        "egregora_dir", "rag_dir", "lancedb_dir", "cache_dir", "prompts_dir",
        "docs_dir", "posts_dir", "profiles_dir", "media_dir", "journal_dir",
        mode="after",
    )
    @classmethod
    def validate_safe_path(cls, v: str) -> str:
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
    """Reader agent configuration."""

    enabled: bool = Field(
        default=False,
        description="Enable reader agent for post quality evaluation",
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
    """Feature flags."""

    ranking_enabled: bool = Field(
        default=False,
        description="Enable Elo-based post ranking",
    )
    annotations_enabled: bool = Field(
        default=True,
        description="Enable conversation annotations/threading",
    )


class QuotaSettings(BaseModel):
    """Configuration for LLM usage budgets."""

    daily_llm_requests: int = Field(
        default=DEFAULT_DAILY_LLM_REQUESTS,
        ge=1,
        description="Soft limit for daily LLM calls",
    )
    per_second_limit: float = Field(
        default=DEFAULT_PER_SECOND_LIMIT,
        ge=0.01,
        description="Maximum number of LLM calls allowed per second",
    )
    concurrency: int = Field(
        default=DEFAULT_CONCURRENCY,
        ge=1,
        le=20,
        description="Maximum number of simultaneous LLM tasks",
    )


class EgregoraConfig(BaseSettings):
    """Root configuration for Egregora V3."""

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

    model_config = SettingsConfigDict(
        extra="forbid",
        validate_assignment=True,
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
    def load(cls, site_root: Path | None = None) -> EgregoraConfig:
        return load_egregora_config(site_root)

    @classmethod
    def from_cli_overrides(cls, base_config: EgregoraConfig, **cli_args: Any) -> EgregoraConfig:
        builder = ConfigOverrideBuilder(base_config)

        from_date = cli_args.get("from_date")
        to_date = cli_args.get("to_date")
        builder.with_pipeline(
            step_size=cli_args.get("step_size"),
            step_unit=cli_args.get("step_unit"),
            overlap_ratio=cli_args.get("overlap_ratio"),
            timezone=str(cli_args["timezone"]) if cli_args.get("timezone") is not None else None,
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
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


# ============================================================================
# Configuration Loading and Saving
# ============================================================================


def find_egregora_config(start_dir: Path) -> Path | None:
    current = start_dir.expanduser().resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / ".egregora" / "config.yml"
        if config_path.exists():
            return config_path
    return None


def _collect_env_override_paths() -> set[tuple[str, ...]]:
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
        base_config = EgregoraConfig()
        base_dict = base_config.model_dump(mode="json")

        env_override_paths = _collect_env_override_paths()
        merged = _merge_config(base_dict, file_data, env_override_paths)

        config = EgregoraConfig.model_validate(merged)
        # Inject site_root into paths for V3 compatibility
        config.paths.site_root = site_root
        return config
    except ValidationError as e:
        logger.exception("Configuration validation failed for %s:", config_path)
        return create_default_config(site_root)


def create_default_config(site_root: Path) -> EgregoraConfig:
    config = EgregoraConfig()
    # Inject site_root
    config.paths.site_root = site_root
    save_egregora_config(config, site_root)
    return config


def save_egregora_config(config: EgregoraConfig, site_root: Path) -> Path:
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
    return config_path


# ============================================================================
# Runtime Configuration Dataclasses
# ============================================================================

@dataclass
class RuntimeContext:
    output_dir: Annotated[Path, "Directory for the generated site"]
    input_file: Annotated[Path | None, "Path to the chat export file"] = None
    model_override: Annotated[str | None, "Model override from CLI"] = None
    debug: Annotated[bool, "Enable debug logging"] = False

    @property
    def input_path(self) -> Path | None:
        return self.input_file


@dataclass
class WriterRuntimeConfig:
    posts_dir: Annotated[Path, "Directory to save posts"]
    profiles_dir: Annotated[Path, "Directory to save profiles"]
    rag_dir: Annotated[Path, "Directory for RAG data"]
    model_config: Annotated[object | None, "Model configuration"] = None
    enable_rag: Annotated[bool, "Enable RAG"] = True


@dataclass
class MediaEnrichmentContext:
    media_type: Annotated[str, "The type of media"]
    media_filename: Annotated[str, "The filename of the media"]
    author: Annotated[str, "The author of the message containing the media"]
    timestamp: Annotated[str, "The timestamp of the message"]
    nearby_messages: Annotated[str, "Messages sent before and after the media"]
    ocr_text: Annotated[str, "Text extracted from the media via OCR"] = ""
    detected_objects: Annotated[str, "Objects detected in the media"] = ""


@dataclass
class EnrichmentRuntimeConfig:
    client: Annotated[object, "The Gemini client"]
    output_dir: Annotated[Path, "The directory to save enriched data"]
    model: Annotated[str, "The Gemini model to use for enrichment"] = DEFAULT_MODEL


@dataclass
class PipelineEnrichmentConfig:
    batch_threshold: int = 10
    max_enrichments: int = 500
    enable_url: bool = True
    enable_media: bool = True

    def __post_init__(self) -> None:
        if self.batch_threshold < 1:
            raise ValueError(f"batch_threshold must be >= 1, got {self.batch_threshold}")
        if self.max_enrichments < 0:
            raise ValueError(f"max_enrichments must be >= 0, got {self.max_enrichments}")

    @classmethod
    def from_cli_args(cls, **kwargs: Any) -> PipelineEnrichmentConfig:
        return cls(
            batch_threshold=int(kwargs.get("batch_threshold", 10)),
            max_enrichments=int(kwargs.get("max_enrichments", 500)),
            enable_url=bool(kwargs.get("enable_url", True)),
            enable_media=bool(kwargs.get("enable_media", True)),
        )

# Model type literal
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
    "get_openrouter_api_key",
    "openrouter_api_key_status",
]
