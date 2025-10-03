"""Configuration helpers for the newsletter pipeline."""

from __future__ import annotations

import copy
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
class RAGConfig:
    """Configuration for the newsletter RAG subsystem."""

    enabled: bool = False
    top_k: int = 5
    min_similarity: float = 0.65
    exclude_recent_days: int = 7
    max_context_chars: int = 1200
    max_keywords: int = 8
    use_mcp: bool = True
    mcp_command: str = "uv"
    mcp_args: tuple[str, ...] = (
        "run",
        "python",
        "-m",
        "egregora.mcp_server.server",
    )
    use_gemini_embeddings: bool = False
    embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = 768
    embedding_cache_enabled: bool = True
    use_batch_api: bool = False


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


@dataclass(slots=True)
class PrivacyConfig:
    """Configuration for optional newsletter privacy reviews."""

    double_check_newsletter: bool = False
    review_model: str | None = None


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
        rag: RAGConfig | None = None,
        privacy: PrivacyConfig | None = None,
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
            privacy=(copy.deepcopy(privacy) if privacy else PrivacyConfig()),
        )


__all__ = [
    "DEFAULT_GROUP_NAME",
    "DEFAULT_MODEL",
    "DEFAULT_TIMEZONE",
    "AnonymizationConfig",
    "CacheConfig",
    "EnrichmentConfig",
    "PrivacyConfig",
    "RAGConfig",
    "PipelineConfig",
]
