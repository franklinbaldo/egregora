"""Configuration helpers for the newsletter pipeline."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

from .anonymizer import FormatType
from .rag.config import RAGConfig
from .models import MergeConfig


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
    
    # Virtual groups (merges)
    merges: dict[str, MergeConfig] = field(default_factory=dict)
    
    # If True, skip real groups that are part of virtual groups
    skip_real_if_in_virtual: bool = True

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
        merges: dict[str, MergeConfig] | None = None,
        skip_real_if_in_virtual: bool = True,
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
            merges=(copy.deepcopy(merges) if merges else {}),
            skip_real_if_in_virtual=skip_real_if_in_virtual,
        )

    @classmethod
    def from_toml(cls, toml_path: Path) -> "PipelineConfig":
        """Load configuration from TOML file."""
        import tomllib
        
        with open(toml_path, 'rb') as f:
            data = tomllib.load(f)
        
        # Parse merges
        merges = {}
        for slug, merge_data in data.get('merges', {}).items():
            merges[slug] = MergeConfig(
                name=merge_data['name'],
                source_groups=merge_data['groups'],
                tag_style=merge_data.get('tag_style', 'emoji'),
                group_emojis=merge_data.get('emojis', {}),
                model_override=merge_data.get('model'),
            )
        
        # Parse directories
        dirs = data.get('directories', {})
        pipeline = data.get('pipeline', {})
        
        return cls(
            zips_dir=Path(dirs.get('zips_dir', 'data/whatsapp_zips')),
            newsletters_dir=Path(dirs.get('newsletters_dir', 'newsletters')),
            media_dir=Path(dirs.get('media_dir', 'media')),
            group_name=pipeline.get('group_name', DEFAULT_GROUP_NAME),
            model=pipeline.get('model', DEFAULT_MODEL),
            timezone=ZoneInfo(pipeline.get('timezone', DEFAULT_TIMEZONE)),
            enrichment=EnrichmentConfig(**data.get('enrichment', {})),
            cache=CacheConfig(**data.get('cache', {})),
            anonymization=AnonymizationConfig(**data.get('anonymization', {})),
            rag=RAGConfig(**data.get('rag', {})),
            merges=merges,
            skip_real_if_in_virtual=pipeline.get('skip_real_if_in_virtual', True),
        )


__all__ = [
    "DEFAULT_GROUP_NAME",
    "DEFAULT_MODEL",
    "DEFAULT_TIMEZONE",
    "AnonymizationConfig",
    "CacheConfig",
    "EnrichmentConfig",
    "PipelineConfig",
    "RAGConfig",
]
