"""Configuration helpers powered by :mod:`pydantic`."""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping
from datetime import tzinfo
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    SecretStr,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import (
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    SecretsSettingsSource,
    TomlConfigSettingsSource,
)

from .anonymizer import FormatType
from .models import MergeConfig
from .rag.config import RAGConfig, sanitize_rag_config_payload
from .types import GroupSlug

DEFAULT_MODEL = "gemini-flash-lite-latest"
DEFAULT_TIMEZONE = "America/Porto_Velho"

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
            raise ValueError("output_format must be one of 'human', 'short' or 'full'")
        return candidate  # type: ignore[return-value]


class ProfilesConfig(BaseModel):
    """Configuration for participant profile generation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True
    profiles_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("data/profiles"))
    docs_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("docs/profiles"))
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


class PipelineTomlSettingsSource(TomlConfigSettingsSource):
    """Normalise ``egregora.toml`` payloads for :class:`PipelineConfig`."""

    def __call__(self) -> dict[str, Any]:
        raw = super().__call__()
        if not raw:
            return {}

        payload: dict[str, Any] = {}

        directories = raw.get("directories")
        if isinstance(directories, Mapping):
            for key in ("zips_dir", "posts_dir"):
                value = directories.get(key)
                if value is not None:
                    payload[key] = value

        pipeline_section = raw.get("pipeline")
        if isinstance(pipeline_section, Mapping):
            for key, value in pipeline_section.items():
                if value is None:
                    continue
                if key == "remote_source":
                    payload[key] = value
                else:
                    payload[key] = value

        for section in (
            "llm",
            "enrichment",
            "cache",
            "anonymization",
            "profiles",
            "system_classifier",
        ):
            section_value = raw.get(section)
            if section_value is not None:
                payload[section] = section_value

        rag_section = raw.get("rag")
        if isinstance(rag_section, Mapping):
            payload["rag"] = sanitize_rag_config_payload(dict(rag_section))
        elif rag_section is not None:
            payload["rag"] = rag_section

        merges = raw.get("merges")
        if merges is not None:
            payload["merges"] = merges

        return payload


class PipelineConfig(BaseSettings):
    """Runtime configuration for the post pipeline."""

    model_config = SettingsConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,
        env_nested_delimiter="__",
    )

    default_toml_path: ClassVar[Path | None] = Path("egregora.toml")

    zips_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("data/whatsapp_zips"))
    posts_dir: Path = Field(default_factory=lambda: _ensure_safe_directory("data"))
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
    merges: dict[GroupSlug, MergeConfig] = Field(default_factory=dict)
    skip_real_if_in_virtual: bool = True
    system_message_filters_file: Path | None = None
    use_dataframe_pipeline: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "use_dataframe_pipeline",
            "EGREGORA_USE_DF_PIPELINE",
        ),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        dotenv_settings: DotEnvSettingsSource,
        file_secret_settings: SecretsSettingsSource,
    ) -> tuple[InitSettingsSource, ...]:
        toml_source = PipelineTomlSettingsSource(
            settings_cls,
            getattr(settings_cls, "default_toml_path", None),
        )
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            toml_source,
            file_secret_settings,
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

    @classmethod
    def with_defaults(  # noqa: PLR0912, PLR0913
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
    ) -> PipelineConfig:
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
        return cls.load(overrides=payload, use_default_toml=False)

    @classmethod
    def load(
        cls,
        *,
        toml_path: Path | None = None,
        overrides: Mapping[str, Any] | None = None,
        use_default_toml: bool = True,
    ) -> PipelineConfig:
        if toml_path is not None:
            if not toml_path.exists():
                raise FileNotFoundError(toml_path)
            if not toml_path.is_file():
                raise ValueError(f"Configuration path '{toml_path}' must be a file")

        original_path = cls.default_toml_path
        if toml_path is not None:
            cls.default_toml_path = toml_path
        elif not use_default_toml:
            cls.default_toml_path = None

        try:
            return cls(**dict(overrides or {}))
        finally:
            cls.default_toml_path = original_path

    @classmethod
    def from_toml(cls, toml_path: Path) -> PipelineConfig:
        """Backwards compatible helper that loads settings from ``toml_path``."""

        return cls.load(toml_path=toml_path)

    def safe_dict(self) -> dict[str, Any]:
        """Return a dictionary representation with sensitive values redacted."""

        data = copy.deepcopy(self.model_dump(mode="python", exclude_none=True, round_trip=True))
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
        (base_dir / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    )

    try:
        resolved.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(
            f"Directory path '{candidate}' must reside within the project directory"
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
    "RemoteSourceConfig",
    "RAGConfig",
]
