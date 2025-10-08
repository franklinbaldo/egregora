"""Configuration helpers powered by :mod:`pydantic`."""

from __future__ import annotations

from datetime import tzinfo
import os
import copy
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
)
from pydantic_settings import BaseSettings

from .anonymizer import FormatType
from .models import MergeConfig
from .rag.config import RAGConfig, sanitize_rag_config_payload

DEFAULT_MODEL = "gemini-flash-lite-latest"
DEFAULT_TIMEZONE = "America/Porto_Velho"

_VALID_TAG_STYLES = {"emoji", "brackets", "prefix"}


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


class SystemClassifierConfig(BaseModel):
    """Settings for the system/noise message classifier."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    model: str = DEFAULT_MODEL
    max_llm_calls: int | None = 200
    token_budget: int | None = 20000
    retry_attempts: int = 2


class EnrichmentConfig(BaseModel):
    """Configuration specific to the enrichment subsystem."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    enrichment_model: str = "gemini-2.0-flash-exp"
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
    metrics_csv_path: Path | None = Field(
        default_factory=lambda: Path("metrics/enrichment_run.csv")
    )

    @field_validator("metrics_csv_path", mode="before")
    @classmethod
    def _validate_metrics_path(cls, value: Any) -> Path | None:
        if value is None or value == "":
            return None
        return Path(value)


class AnonymizationConfig(BaseModel):
    """Configuration for author anonymisation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    output_format: FormatType = "human"

    @field_validator("output_format", mode="before")
    @classmethod
    def _validate_output_format(cls, value: Any) -> FormatType:
        candidate = str(value)
        if candidate not in ("human", "short", "full"):
            raise ValueError(
                "output_format must be one of 'human', 'short' or 'full'"
            )
        return candidate  # type: ignore[return-value]


class ProfilesConfig(BaseModel):
    """Configuration for participant profile generation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    profiles_dir: Path = Field(
        default_factory=lambda: _ensure_safe_directory("data/profiles")
    )
    docs_dir: Path = Field(
        default_factory=lambda: _ensure_safe_directory("docs/profiles")
    )
    min_messages: int = 2
    min_words_per_message: int = 15
    history_days: int = 5
    max_profiles_per_run: int = 3
    decision_model: str = "models/gemini-flash-latest"
    rewrite_model: str = "models/gemini-flash-latest"
    max_api_retries: int = 3
    minimum_retry_seconds: float = 30.0

    @field_validator("profiles_dir", "docs_dir", mode="before")
    @classmethod
    def _validate_directories(cls, value: Any) -> Path:
        return _ensure_safe_directory(value)

    @field_validator(
        "min_messages",
        "min_words_per_message",
        "history_days",
        "max_profiles_per_run",
        "max_api_retries",
    )
    @classmethod
    def _validate_positive(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("profile thresholds must be positive integers")
        return ivalue

    @field_validator("minimum_retry_seconds")
    @classmethod
    def _validate_retry_seconds(cls, value: Any) -> float:
        fvalue = float(value)
        if fvalue < 0:
            raise ValueError("minimum_retry_seconds must be non-negative")
        return fvalue




def _default_remote_gdrive_url() -> SecretStr | None:
    for key in ("PIPELINE__REMOTE_SOURCE__GDRIVE_URL", "REMOTE_SOURCE__GDRIVE_URL"):
        value = os.getenv(key)
        if value is None:
            continue
        stripped = value.strip()
        if stripped:
            return SecretStr(stripped)
    return None

class RemoteSourceConfig(BaseModel):
    """Configuration for remote ZIP sources such as Google Drive."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    gdrive_url: SecretStr | None = Field(
        default_factory=_default_remote_gdrive_url,
        validation_alias=AliasChoices(
            "gdrive_url",
            "REMOTE_SOURCE__GDRIVE_URL",
            "PIPELINE__REMOTE_SOURCE__GDRIVE_URL",
        ),
    )

    @field_validator("gdrive_url", mode="before")
    @classmethod
    def _validate_gdrive_url(cls, value: Any) -> SecretStr | None | str:
        if value is None:
            return None

        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        raw = raw.strip()
        if not raw:
            return None

        from urllib.parse import urlparse

        parsed = urlparse(raw)
        if parsed.scheme not in {"https"} or not parsed.netloc:
            raise ValueError("gdrive_url must be a valid HTTPS URL")
        return value

    def get_gdrive_url(self) -> str | None:
        """Return the raw Google Drive URL, if configured."""

        if self.gdrive_url is None:
            return None
        return self.gdrive_url.get_secret_value()

    def masked_gdrive_url(self) -> str | None:
        """Return a masked value suitable for logs and diagnostics."""

        if self.gdrive_url is None:
            return None
        return str(self.gdrive_url)


class PipelineConfig(BaseSettings):
    """Runtime configuration for the post pipeline."""

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,
    )

    zips_dir: Path = Field(
        default_factory=lambda: _ensure_safe_directory("data/whatsapp_zips")
    )
    posts_dir: Path = Field(
        default_factory=lambda: _ensure_safe_directory("data")
    )
    post_language: str = "pt-BR"
    default_post_author: str = "egregora"
    media_url_prefix: str | None = None
    model: str = DEFAULT_MODEL
    timezone: ZoneInfo = Field(default_factory=lambda: ZoneInfo(DEFAULT_TIMEZONE))
    llm: LLMConfig = Field(default_factory=LLMConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    system_classifier: SystemClassifierConfig = Field(default_factory=SystemClassifierConfig)
    anonymization: AnonymizationConfig = Field(default_factory=AnonymizationConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    profiles: ProfilesConfig = Field(default_factory=ProfilesConfig)
    remote_source: RemoteSourceConfig = Field(default_factory=RemoteSourceConfig)
    merges: dict[str, MergeConfig] = Field(default_factory=dict)
    skip_real_if_in_virtual: bool = True
    system_message_filters_file: Path | None = None
    use_dataframe_pipeline: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "use_dataframe_pipeline",
            "EGREGORA_USE_DF_PIPELINE",
        ),
    )

    @field_validator("timezone", mode="before")
    @classmethod
    def _coerce_timezone(cls, value: Any) -> ZoneInfo:
        if isinstance(value, ZoneInfo):
            return value
        if isinstance(value, str):
            return ZoneInfo(value)
        raise TypeError("timezone must be an IANA timezone string or ZoneInfo")

    @field_validator("zips_dir", "posts_dir", mode="before")
    @classmethod
    def _validate_directories(cls, value: Any) -> Path:
        return _ensure_safe_directory(value)

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

    @field_validator("system_classifier", mode="before")
    @classmethod
    def _validate_system_classifier(cls, value: Any) -> SystemClassifierConfig:
        if isinstance(value, SystemClassifierConfig):
            return value
        if isinstance(value, dict):
            return SystemClassifierConfig(**value)
        raise TypeError("system_classifier configuration must be a mapping")

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
            return RAGConfig(**sanitize_rag_config_payload(value))
        raise TypeError("rag configuration must be a mapping")

    @field_validator("profiles", mode="before")
    @classmethod
    def _validate_profiles(cls, value: Any) -> ProfilesConfig:
        if isinstance(value, ProfilesConfig):
            return value
        if isinstance(value, dict):
            return ProfilesConfig(**value)
        raise TypeError("profiles configuration must be a mapping")

    @field_validator("remote_source", mode="before")
    @classmethod
    def _validate_remote_source(cls, value: Any) -> RemoteSourceConfig:
        if value is None:
            return RemoteSourceConfig()
        if isinstance(value, RemoteSourceConfig):
            return value
        if isinstance(value, dict):
            return RemoteSourceConfig(**value)
        raise TypeError("remote_source configuration must be a mapping or RemoteSourceConfig")

    @field_validator("merges", mode="before")
    @classmethod
    def _validate_merges(cls, value: Any) -> dict[str, MergeConfig]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("merges must be a mapping")

        merges: dict[str, MergeConfig] = {}
        for slug, payload in value.items():
            if not isinstance(payload, dict):
                raise TypeError(f"Merge '{slug}' must be a mapping")
            tag_style = payload.get("tag_style", "emoji")
            if tag_style not in _VALID_TAG_STYLES:
                raise ValueError(
                    f"Invalid tag_style '{tag_style}' for merge '{slug}'"
                )
            groups = payload.get("groups", [])
            if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
                raise ValueError(f"Merge '{slug}' groups must be a list of strings")
            if not groups:
                raise ValueError(
                    f"Merge '{slug}' must include at least one source group"
                )
            merges[slug] = MergeConfig(
                name=payload["name"],
                source_groups=list(groups),
                tag_style=tag_style,  # type: ignore[arg-type]
                group_emojis=payload.get("emojis", {}),
                model_override=payload.get("model"),
            )
        return merges

    @classmethod
    def with_defaults(
        cls,
        *,
        zips_dir: Path | None = None,
        posts_dir: Path | None = None,
        media_url_prefix: str | None = None,
        model: str | None = None,
        timezone: tzinfo | None = None,
        llm: LLMConfig | dict[str, Any] | None = None,
        enrichment: EnrichmentConfig | dict[str, Any] | None = None,
        cache: CacheConfig | dict[str, Any] | None = None,
        system_classifier: SystemClassifierConfig | dict[str, Any] | None = None,
        anonymization: AnonymizationConfig | dict[str, Any] | None = None,
        rag: RAGConfig | dict[str, Any] | None = None,
        profiles: ProfilesConfig | dict[str, Any] | None = None,
        remote_source: RemoteSourceConfig | dict[str, Any] | None = None,
        merges: dict[str, Any] | None = None,
        skip_real_if_in_virtual: bool | None = None,
        system_message_filters_file: Path | None = None,
        use_dataframe_pipeline: bool | None = None,
    ) -> "PipelineConfig":
        payload: dict[str, Any] = {}
        if zips_dir is not None:
            payload["zips_dir"] = zips_dir
        if posts_dir is not None:
            payload["posts_dir"] = posts_dir
        if model is not None:
            payload["model"] = model
        if media_url_prefix is not None:
            payload["media_url_prefix"] = media_url_prefix
        if timezone is not None:
            payload["timezone"] = timezone
        if llm is not None:
            payload["llm"] = llm
        if enrichment is not None:
            payload["enrichment"] = enrichment
        if cache is not None:
            payload["cache"] = cache
        if system_classifier is not None:
            payload["system_classifier"] = system_classifier
        if anonymization is not None:
            payload["anonymization"] = anonymization
        if rag is not None:
            payload["rag"] = rag
        if profiles is not None:
            payload["profiles"] = profiles
        if remote_source is not None:
            payload["remote_source"] = remote_source
        if merges is not None:
            payload["merges"] = merges
        if skip_real_if_in_virtual is not None:
            payload["skip_real_if_in_virtual"] = skip_real_if_in_virtual
        if system_message_filters_file is not None:
            payload["system_message_filters_file"] = system_message_filters_file
        if use_dataframe_pipeline is not None:
            payload["use_dataframe_pipeline"] = use_dataframe_pipeline
        return cls(**payload)

    @classmethod
    def from_toml(cls, toml_path: Path) -> "PipelineConfig":
        data = _load_toml_data(toml_path)
        payload: dict[str, Any] = {}

        directories = data.get("directories", {})
        if isinstance(directories, dict):
            for key in ("zips_dir", "posts_dir"):
                value = directories.get(key)
                if value is not None:
                    payload[key] = value

        pipeline = data.get("pipeline", {})
        if isinstance(pipeline, dict):
            for key in ("model", "skip_real_if_in_virtual", "media_url_prefix"):
                value = pipeline.get(key)
                if value is not None:
                    payload[key] = value
            timezone_value = pipeline.get("timezone")
            if timezone_value is not None:
                payload["timezone"] = timezone_value
            remote_source = pipeline.get("remote_source")
            if remote_source is not None:
                payload["remote_source"] = remote_source

        for section in ("llm", "enrichment", "cache", "anonymization", "rag", "profiles"):
            if section in data:
                section_value = data[section]
                if section == "rag" and isinstance(section_value, dict):
                    payload[section] = sanitize_rag_config_payload(section_value)
                else:
                    payload[section] = section_value

        if "merges" in data:
            payload["merges"] = data["merges"]

        return cls(**payload)

    def safe_dict(self) -> dict[str, Any]:
        """Return a dictionary representation with sensitive values redacted."""

        data = copy.deepcopy(
            self.model_dump(mode="python", exclude_none=True, round_trip=True)
        )
        remote = data.get("remote_source")
        if isinstance(remote, dict) and "gdrive_url" in remote:
            remote["gdrive_url"] = self.remote_source.masked_gdrive_url()
        return data


def _ensure_safe_directory(path_value: Any) -> Path:
    """Validate and normalise directory paths loaded from configuration."""

    candidate = Path(path_value).expanduser()

    if any(part == ".." for part in candidate.parts):
        raise ValueError(f"Directory path '{candidate}' must not contain '..'")

    base_dir = Path.cwd().resolve()
    resolved = (
        (base_dir / candidate).resolve()
        if not candidate.is_absolute()
        else candidate.resolve()
    )

    try:
        resolved.relative_to(base_dir)
    except ValueError:
        raise ValueError(
            f"Directory path '{candidate}' must reside within the project directory"
        )

    return resolved


_MAX_TOML_BYTES = 512 * 1024


def _load_toml_data(toml_path: Path) -> dict[str, Any]:
    """Load TOML data from ``toml_path`` with strict validation."""

    import tomllib

    if not toml_path.exists():
        raise FileNotFoundError(toml_path)
    if not toml_path.is_file():
        raise ValueError(f"Configuration path '{toml_path}' must be a file")

    with toml_path.open("rb") as fh:
        content = fh.read(_MAX_TOML_BYTES + 1)

    if len(content) > _MAX_TOML_BYTES:
        raise ValueError(
            f"Configuration file '{toml_path}' exceeds maximum size of {_MAX_TOML_BYTES} bytes"
        )

    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Configuration file '{toml_path}' must be UTF-8 encoded"
        ) from exc

    data = tomllib.loads(decoded)

    if not isinstance(data, dict):
        raise ValueError("Top-level TOML structure must be a table")

    return data


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_TIMEZONE",
    "AnonymizationConfig",
    "CacheConfig",
    "EnrichmentConfig",
    "LLMConfig",
    "PipelineConfig",
    "ProfilesConfig",
    "RemoteSourceConfig",
    "RAGConfig",
]
