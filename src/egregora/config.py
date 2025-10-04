"""Configuration helpers for the newsletter pipeline and backlog tooling."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import tzinfo
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import yaml

from .anonymizer import FormatType
from .rag.config import RAGConfig


DEFAULT_GROUP_NAME = "RC LatAm"
DEFAULT_MODEL = "gemini-flash-lite-latest"
DEFAULT_TIMEZONE = "America/Porto_Velho"


@dataclass(slots=True)
class CacheConfig:
    """Configuration for the persistent enrichment cache."""

    enabled: bool = True
    cache_dir: Path = Path("cache")
    auto_cleanup_days: int | None = 90
    max_disk_mb: int | None = 100

@dataclass(slots=True)
class EnrichmentConfig:
    """Configuration specific to the enrichment subsystem."""

    enabled: bool = True
    enrichment_model: str = "gemini-2.0-flash-exp"
    max_links: int = 50
    context_window: int = 3
    relevance_threshold: int = 2
    max_concurrent_analyses: int = 5
    max_total_enrichment_time: float = 120.0


@dataclass(slots=True)
class AnonymizationConfig:
    """Configuration for author anonymization.

    Attributes:
        enabled: Controls whether author names are converted before prompting.
        output_format: Style of the anonymized identifiers:
            - ``"human"`` → formato legível (ex.: ``Member-A1B2``).
            - ``"short"`` → 8 caracteres hexadecimais (ex.: ``a1b2c3d4``).
            - ``"full"`` → UUID completo.
    """

    enabled: bool = True
    output_format: FormatType = "human"


@dataclass(slots=True)
class PipelineConfig:
    """Runtime configuration for the newsletter pipeline."""

    zips_dir: Path
    newsletters_dir: Path
    media_dir: Path
    group_name: str
    model: str
    timezone: tzinfo
    enrichment: EnrichmentConfig
    cache: CacheConfig
    anonymization: AnonymizationConfig
    rag: RAGConfig

    @classmethod
    def with_defaults(
        cls,
        *,
        zips_dir: Path | None = None,
        newsletters_dir: Path | None = None,
        group_name: str | None = None,
        model: str | None = None,
        timezone: tzinfo | None = None,
        enrichment: EnrichmentConfig | None = None,
        cache: CacheConfig | None = None,
        anonymization: AnonymizationConfig | None = None,
        rag: RAGConfig | None = None,
        media_dir: Path | None = None,
    ) -> "PipelineConfig":
        """Create a configuration using project defaults."""

        return cls(
            zips_dir=(zips_dir or Path("data/whatsapp_zips")).expanduser(),
            newsletters_dir=(newsletters_dir or Path("newsletters")).expanduser(),
            media_dir=(media_dir or Path("media")).expanduser(),
            group_name=group_name or DEFAULT_GROUP_NAME,
            model=model or DEFAULT_MODEL,
            timezone=timezone or ZoneInfo(DEFAULT_TIMEZONE),
            enrichment=(copy.deepcopy(enrichment) if enrichment else EnrichmentConfig()),
            cache=(copy.deepcopy(cache) if cache else CacheConfig()),
            anonymization=(
                copy.deepcopy(anonymization) if anonymization else AnonymizationConfig()
            ),
            rag=(copy.deepcopy(rag) if rag else RAGConfig()),
        )


@dataclass(slots=True)
class BacklogProcessingConfig:
    """Configuration related to batch execution parameters."""

    delay_between_days: int = 2
    max_retries: int = 3
    timeout_per_day: int = 300


@dataclass(slots=True)
class BacklogAPIConfig:
    """API throttling controls for batch processing."""

    gemini_rpm_limit: int = 60
    pause_on_rate_limit: bool = True
    rate_limit_pause: int = 60


@dataclass(slots=True)
class BacklogEnrichmentConfig:
    """Configuration for enrichment when running backlog jobs."""

    enabled: bool = True
    url_timeout: int = 10
    max_urls_per_day: int = 50


@dataclass(slots=True)
class BacklogRAGConfig:
    """Configuration for contextual retrieval during backlog processing."""

    use_previous_context: bool = True
    max_previous_newsletters: int = 5
    use_gemini_embeddings: bool = True


@dataclass(slots=True)
class BacklogLoggingConfig:
    """Logging configuration for backlog utilities."""

    level: str = "INFO"
    file: Path = Path("./cache/backlog_processing.log")
    detailed_per_day: bool = True


@dataclass(slots=True)
class BacklogCheckpointConfig:
    """Checkpoint configuration for resumable backlog processing."""

    enabled: bool = True
    file: Path = Path("./cache/backlog_checkpoint.json")
    backup: bool = True


@dataclass(slots=True)
class BacklogConfig:
    """Top-level configuration for backlog processing."""

    processing: BacklogProcessingConfig = field(default_factory=BacklogProcessingConfig)
    api: BacklogAPIConfig = field(default_factory=BacklogAPIConfig)
    enrichment: BacklogEnrichmentConfig = field(default_factory=BacklogEnrichmentConfig)
    rag: BacklogRAGConfig = field(default_factory=BacklogRAGConfig)
    logging: BacklogLoggingConfig = field(default_factory=BacklogLoggingConfig)
    checkpoint: BacklogCheckpointConfig = field(default_factory=BacklogCheckpointConfig)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any] | None) -> "BacklogConfig":
        """Create a configuration instance from a mapping."""

        if not mapping:
            return cls()

        data = dict(mapping)

        def build(section: str, factory: type) -> Any:
            current = data.get(section, {})
            if isinstance(current, Mapping):
                base = factory()
                for key, value in current.items():
                    if hasattr(base, key):
                        setattr(base, key, value)
                return base
            return factory()

        return cls(
            processing=build("processing", BacklogProcessingConfig),
            api=build("api", BacklogAPIConfig),
            enrichment=build("enrichment", BacklogEnrichmentConfig),
            rag=build("rag", BacklogRAGConfig),
            logging=build("logging", BacklogLoggingConfig),
            checkpoint=build("checkpoint", BacklogCheckpointConfig),
        )


def load_backlog_config(config_path: str | Path | None) -> BacklogConfig:
    """Load backlog configuration from *config_path*.

    Parameters
    ----------
    config_path:
        Path to a YAML configuration file. When ``None`` the default
        ``scripts/backlog_config.yaml`` is used. Missing files yield
        the default configuration.
    """

    candidate = Path(config_path) if config_path else Path("scripts/backlog_config.yaml")
    if not candidate.exists():
        return BacklogConfig()

    raw = candidate.read_text(encoding="utf-8")
    loaded = yaml.safe_load(raw) or {}
    if not isinstance(loaded, Mapping):
        raise ValueError("Configuração de backlog inválida: esperado objeto mapeável.")
    return BacklogConfig.from_mapping(loaded)


__all__ = [
    "DEFAULT_GROUP_NAME",
    "DEFAULT_MODEL",
    "DEFAULT_TIMEZONE",
    "AnonymizationConfig",
    "BacklogAPIConfig",
    "BacklogCheckpointConfig",
    "BacklogConfig",
    "BacklogEnrichmentConfig",
    "BacklogLoggingConfig",
    "BacklogProcessingConfig",
    "BacklogRAGConfig",
    "CacheConfig",
    "EnrichmentConfig",
    "PipelineConfig",
    "RAGConfig",
    "load_backlog_config",
]
