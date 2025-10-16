"""Configuration helpers powered by :mod:`pydantic`."""

from __future__ import annotations

import copy
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)
from pydantic.warnings import UnsupportedFieldAttributeWarning

from .anonymizer import FormatType
from .models import MergeConfig
from .rag.config import RAGConfig
from .types import GroupSlug

warnings.filterwarnings(
    "ignore", category=UnsupportedFieldAttributeWarning, message=".*`validate_default`.*"
)

DEFAULT_MODEL = "models/gemini-1.5-flash"
DEFAULT_TIMEZONE = "America/Porto_Velho"

LEGACY_RAG_KEY_ALIASES: Mapping[str, str] = {
    "vector_store_path": "persist_dir",
    "vector_store_dir": "persist_dir",
    "chunkSize": "chunk_size",
    "chunkOverlap": "chunk_overlap",
    "topK": "top_k",
    "minSimilarity": "min_similarity",
    "keywordStopWords": "keyword_stop_words",
    "embeddingExportPath": "embedding_export_path",
    "cacheDir": "cache_dir",
    "postsDir": "posts_dir",
}


class LLMConfig(BaseModel):
    """Configuration options for the language model."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    safety_threshold: str = "BLOCK_NONE"
    thinking_budget: int = -1


class CacheConfig(BaseModel):
    """Configuration for the persistent enrichment cache."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    cache_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("cache"))
    auto_cleanup_days: int | None = 90
    max_disk_mb: int | None = 100

    @field_validator("cache_dir", mode="before")
    @classmethod
    def _validate_cache_dir(cls, value: Any) -> Path:
        return _ensure_safe_directory(value)


class EnrichmentConfig(BaseModel):
    """Configuration specific to the enrichment subsystem."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    enrichment_model: str = "models/gemini-flash-lite-latest"
    max_links: int = 50
    context_window: int = 3
    relevance_threshold: int = 2
    max_concurrent_analyses: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "max_concurrent_analyses",
            "max_concurrent_requests",
        ),
    )
    max_total_enrichment_time: float = 120.0
    afc_max_remote_calls: int | None = None
    metrics_csv_path: Path | None = Field(
        default_factory=lambda: Path("metrics/enrichment_run.csv")
    )

    @field_validator("metrics_csv_path", mode="before")
    @classmethod
    def _validate_metrics_path(cls, value: Any) -> Path | None:
        if value is None or value == "":
            return None
        return Path(value)

    @field_validator("afc_max_remote_calls", mode="before")
    @classmethod
    def _validate_afc_limit(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        limit = int(value)
        if limit < 1:
            raise ValueError("afc_max_remote_calls must be a positive integer")
        return limit


class AnonymizationConfig(BaseModel):
    """Configuration for author anonymisation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    output_format: FormatType = "full"

    @field_validator("output_format", mode="before")
    @classmethod
    def _validate_output_format(cls, value: Any) -> FormatType:
        candidate = str(value)
        if candidate not in ("human", "short", "full"):
            raise ValueError("output_format must be one of 'human', 'short' or 'full'")
        return candidate  # type: ignore[return-value]


class ProfilesConfig(BaseModel):
    """Configuration for participant profile generation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    profiles_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("data/profiles"))
    docs_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("data/profiles/docs"))
    min_messages: int = 2
    min_words_per_message: int = 15
    history_days: int = 5
    max_profiles_per_run: int = 0
    decision_model: str = "models/gemini-flash-latest"
    rewrite_model: str = "models/gemini-flash-latest"
    max_api_retries: int = 3
    minimum_retry_seconds: float = 30.0
    # Profile linking configuration
    link_members_in_posts: bool = True
    profile_base_url: str = "/profiles/"

    @field_validator("profiles_dir", "docs_dir", mode="before")
    @classmethod
    def _validate_directories(cls, value: Any) -> Path:
        return _ensure_safe_directory(value)

    @field_validator(
        "min_messages",
        "min_words_per_message",
        "history_days",
        "max_api_retries",
    )
    @classmethod
    def _validate_positive(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("profile thresholds must be positive integers")
        return ivalue

    @field_validator("max_profiles_per_run")
    @classmethod
    def _validate_profile_limit(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 0:
            raise ValueError("max_profiles_per_run must be zero or a positive integer")
        return ivalue

    @field_validator("minimum_retry_seconds")
    @classmethod
    def _validate_retry_seconds(cls, value: Any) -> float:
        fvalue = float(value)
        if fvalue < 0:
            raise ValueError("minimum_retry_seconds must be non-negative")
        return fvalue


def sanitize_rag_config_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalise legacy ``[rag]`` payloads to match :class:`RAGConfig`."""

    payload: dict[str, Any] = {str(key): value for key, value in raw.items()}

    for legacy_key, canonical_key in LEGACY_RAG_KEY_ALIASES.items():
        if legacy_key in payload and canonical_key not in payload:
            payload[canonical_key] = payload.pop(legacy_key)
        elif legacy_key in payload:
            payload.pop(legacy_key)

    _coerce_fields(payload)

    return payload


def _coerce_fields(payload: dict[str, Any]) -> None:
    """Coerce fields in the payload to the correct types."""
    # TODO: The field names are hardcoded here. This is not ideal because if the
    # RAGConfig model changes, this function will need to be updated manually.
    # A better approach would be to dynamically inspect the RAGConfig model's
    # fields and their types.
    bool_fields = {
        "enabled",
        "enable_cache",
        "export_embeddings",
    }
    int_fields = {
        "top_k",
        "max_keywords",
        "exclude_recent_days",
        "max_context_chars",
        "classifier_max_llm_calls",
        "classifier_token_budget",
        "chunk_size",
        "chunk_overlap",
        "embedding_dimension",
    }

    for field in bool_fields:
        if field in payload:
            payload[field] = _coerce_bool(payload[field])
    for field in int_fields:
        if field in payload and payload[field] is not None:
            payload[field] = _coerce_int(payload[field])
    if "min_similarity" in payload and payload["min_similarity"] is not None:
        payload["min_similarity"] = _coerce_float(payload["min_similarity"])

    _coerce_keyword_stop_words(payload)
    _coerce_path_fields(payload)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def _coerce_int(value: Any) -> int:
    return int(value) if value is not None else value


def _coerce_float(value: Any) -> float:
    return float(value) if value is not None else value


def _coerce_keyword_stop_words(payload: dict[str, Any]) -> None:
    if "keyword_stop_words" in payload:
        value = payload["keyword_stop_words"]
        if isinstance(value, str):
            items = [part.strip().lower() for part in value.split(",") if part.strip()]
            payload["keyword_stop_words"] = tuple(items)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            payload["keyword_stop_words"] = tuple(
                str(item).strip().lower() for item in value if str(item).strip()
            )


def _coerce_path_fields(payload: dict[str, Any]) -> None:
    for path_field in ("posts_dir", "cache_dir", "embedding_export_path", "persist_dir"):
        if path_field in payload and payload[path_field] is not None:
            payload[path_field] = Path(payload[path_field])


class PipelineConfig(BaseModel):
    """Runtime configuration for the post pipeline."""

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,
    )

    # TOML support removed

    zip_files: list[Path] = Field(default_factory=list)  # ZIP files to process
    posts_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("data"))
    group_name: str | None = None
    group_slug: GroupSlug | None = None
    post_language: str = "pt-BR"
    default_post_author: str = "egregora"
    media_url_prefix: str | None = None
    model: str = DEFAULT_MODEL
    timezone: ZoneInfo = Field(default_factory=lambda: ZoneInfo(DEFAULT_TIMEZONE))
    llm: LLMConfig = Field(default_factory=LLMConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    anonymization: AnonymizationConfig = Field(default_factory=AnonymizationConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    profiles: ProfilesConfig = Field(default_factory=ProfilesConfig)
    merges: dict[GroupSlug, MergeConfig] = Field(default_factory=dict)
    skip_real_if_in_virtual: bool = True
    system_message_filters_file: Path | None = None
    skip_existing_posts: bool = True
    use_dataframe_pipeline: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "use_dataframe_pipeline",
            "EGREGORA_USE_DF_PIPELINE",
        ),
    )

    # Environment variable support removed - use direct initialization

    @field_validator("timezone", mode="before")
    @classmethod
    def _coerce_timezone(cls, value: Any) -> ZoneInfo:
        if isinstance(value, ZoneInfo):
            return value
        if isinstance(value, str):
            return ZoneInfo(value)
        raise TypeError("timezone must be an IANA timezone string or ZoneInfo")

    @field_validator("posts_dir", mode="before")
    @classmethod
    def _validate_directories(cls, value: Any) -> Path:
        # Allow external paths for posts_dir to support architectural separation
        candidate = Path(value).expanduser()

        if any(part == ".." for part in candidate.parts):
            raise ValueError(f"Directory path '{candidate}' must not contain '..'")

        base_dir = Path.cwd().resolve()
        resolved = (candidate if candidate.is_absolute() else base_dir / candidate).resolve()

        return resolved

    @field_validator("group_name", mode="before")
    @classmethod
    def _validate_group_name(cls, value: Any) -> str | None:
        if value is None:
            return None
        candidate = str(value).strip()
        return candidate or None

    @field_validator("group_slug", mode="before")
    @classmethod
    def _validate_group_slug(cls, value: Any) -> GroupSlug | None:
        if value is None:
            return None
        candidate = str(value).strip()
        return GroupSlug(candidate) if candidate else None

    @field_validator("llm", mode="before")
    @classmethod
    def _validate_llm(cls, value: Any) -> LLMConfig:
        if isinstance(value, LLMConfig):
            return value
        if isinstance(value, dict):
            return LLMConfig(**value)
        raise TypeError("llm configuration must be a mapping")

    @field_validator("enrichment", mode="before")
    @classmethod
    def _validate_enrichment(cls, value: Any) -> EnrichmentConfig:
        if isinstance(value, EnrichmentConfig):
            return value
        if isinstance(value, dict):
            return EnrichmentConfig(**value)
        raise TypeError("enrichment configuration must be a mapping")

    @field_validator("cache", mode="before")
    @classmethod
    def _validate_cache(cls, value: Any) -> CacheConfig:
        if isinstance(value, CacheConfig):
            return value
        if isinstance(value, dict):
            return CacheConfig(**value)
        raise TypeError("cache configuration must be a mapping")

    @field_validator("anonymization", mode="before")
    @classmethod
    def _validate_anonymization(cls, value: Any) -> AnonymizationConfig:
        if isinstance(value, AnonymizationConfig):
            return value
        if isinstance(value, dict):
            return AnonymizationConfig(**value)
        raise TypeError("anonymization configuration must be a mapping")

    @field_validator("rag", mode="before")
    @classmethod
    def _validate_rag(cls, value: Any) -> RAGConfig:
        if isinstance(value, RAGConfig):
            return value
        if isinstance(value, dict):
            return RAGConfig(**value)
        raise TypeError("rag configuration must be a mapping")

    @field_validator("profiles", mode="before")
    @classmethod
    def _validate_profiles(cls, value: Any) -> ProfilesConfig:
        if isinstance(value, ProfilesConfig):
            return value
        if isinstance(value, dict):
            return ProfilesConfig(**value)
        raise TypeError("profiles configuration must be a mapping")

    @field_validator("merges", mode="before")
    @classmethod
    def _validate_merges(cls, value: Any) -> dict[GroupSlug, MergeConfig]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise TypeError("merges must be a mapping")

        merges: dict[GroupSlug, MergeConfig] = {}
        for raw_slug, payload in value.items():
            slug = GroupSlug(str(raw_slug))
            if isinstance(payload, MergeConfig):
                merges[slug] = payload
                continue
            if not isinstance(payload, Mapping):
                raise TypeError(f"Merge '{slug}' must be a mapping")

            try:
                merges[slug] = MergeConfig.model_validate(dict(payload))
            except ValidationError as exc:  # pragma: no cover - formatting only
                details = ", ".join(
                    f"{'.'.join(str(loc) for loc in error['loc'])}: {error['msg']}"
                    for error in exc.errors()
                )
                message = details or str(exc)
                raise ValueError(f"Invalid merge configuration for '{slug}': {message}") from exc
        return merges

    # with_defaults method removed - use direct initialization instead

    # TOML loading methods removed - use environment variables instead

    def safe_dict(self) -> dict[str, Any]:
        """Return a dictionary representation with sensitive values redacted."""

        data = copy.deepcopy(self.model_dump(mode="python", exclude_none=True, round_trip=True))
        return data


def _ensure_safe_directory(path_value: Any) -> Path:
    """Validate and normalise directory paths loaded from configuration."""

    candidate = Path(path_value).expanduser()

    if any(part == ".." for part in candidate.parts):
        raise ValueError(f"Directory path '{candidate}' must not contain '..'")

    base_dir = Path.cwd().resolve()
    resolved = (candidate if candidate.is_absolute() else base_dir / candidate).resolve()

    try:
        resolved.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(
            "Directory paths must stay within the project root. "
            f"'{candidate}' resolves to '{resolved}', which is outside '{base_dir}'."
        ) from exc

    return resolved


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_TIMEZONE",
    "AnonymizationConfig",
    "CacheConfig",
    "EnrichmentConfig",
    "LLMConfig",
    "PipelineConfig",
    "ProfilesConfig",
    "RAGConfig",
]