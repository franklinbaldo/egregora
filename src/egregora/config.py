"""Configuration helpers for the newsletter pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

from .anonymizer import FormatType


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

    def clone(self) -> "CacheConfig":
        return CacheConfig(
            enabled=self.enabled,
            cache_dir=self.cache_dir,
            auto_cleanup_days=self.auto_cleanup_days,
            max_disk_mb=self.max_disk_mb,
        )


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

    def clone(self) -> "EnrichmentConfig":
        """Return a shallow copy that can be mutated safely."""

        return EnrichmentConfig(
            enabled=self.enabled,
            enrichment_model=self.enrichment_model,
            max_links=self.max_links,
            context_window=self.context_window,
            relevance_threshold=self.relevance_threshold,
            max_concurrent_analyses=self.max_concurrent_analyses,
            max_total_enrichment_time=self.max_total_enrichment_time,
        )


@dataclass(slots=True)
class AnonymizationConfig:
    """Configuration for author anonymization.

    Attributes:
        enabled: Controls whether author names are converted before prompting.
        output_format: Style of the anonymized identifiers:
            - ``"human"`` → formato legível (ex.: ``User-A1B2``).
            - ``"short"`` → 8 caracteres hexadecimais (ex.: ``a1b2c3d4``).
            - ``"full"`` → UUID completo.
    """

    enabled: bool = True
    output_format: FormatType = "human"

    def clone(self) -> "AnonymizationConfig":
        return AnonymizationConfig(
            enabled=self.enabled,
            output_format=self.output_format,
        )


@dataclass(slots=True)
class PrivacyConfig:
    """Configuration for optional newsletter privacy reviews."""

    double_check_newsletter: bool = False
    review_model: str | None = None

    def clone(self) -> "PrivacyConfig":
        return PrivacyConfig(
            double_check_newsletter=self.double_check_newsletter,
            review_model=self.review_model,
        )


@dataclass(slots=True)
class PipelineConfig:
    """Runtime configuration for the newsletter pipeline."""

    zips_dir: Path
    newsletters_dir: Path
    group_name: str
    model: str
    timezone: tzinfo
    enrichment: EnrichmentConfig
    cache: CacheConfig
    anonymization: AnonymizationConfig
    privacy: PrivacyConfig

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
        privacy: PrivacyConfig | None = None,
    ) -> "PipelineConfig":
        """Create a configuration using project defaults."""

        return cls(
            zips_dir=(zips_dir or Path("data/whatsapp_zips")).expanduser(),
            newsletters_dir=(newsletters_dir or Path("newsletters")).expanduser(),
            group_name=group_name or DEFAULT_GROUP_NAME,
            model=model or DEFAULT_MODEL,
            timezone=timezone or ZoneInfo(DEFAULT_TIMEZONE),
            enrichment=(enrichment.clone() if enrichment else EnrichmentConfig()),
            cache=(cache.clone() if cache else CacheConfig()),
            anonymization=(
                anonymization.clone() if anonymization else AnonymizationConfig()
            ),
            privacy=(privacy.clone() if privacy else PrivacyConfig()),
        )


__all__ = [
    "DEFAULT_GROUP_NAME",
    "DEFAULT_MODEL",
    "DEFAULT_TIMEZONE",
    "AnonymizationConfig",
    "CacheConfig",
    "EnrichmentConfig",
    "PrivacyConfig",
    "PipelineConfig",
]
