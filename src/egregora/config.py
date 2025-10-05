"""Configuration helpers for the newsletter pipeline."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .anonymizer import FormatType
from .rag.config import RAGConfig
from .models import MergeConfig

DEFAULT_MODEL = "gemini-flash-lite-latest"
DEFAULT_TIMEZONE = "America/Porto_Velho"
DEFAULT_THINKING_BUDGET = -1  # Unlimited thinking


@dataclass(slots=True)
class LLMConfig:
    """Configuration for the language model."""

    safety_threshold: str = "BLOCK_NONE"
    thinking_budget: int = DEFAULT_THINKING_BUDGET


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


_VALID_TAG_STYLES = {"emoji", "brackets", "prefix"}


@dataclass(slots=True)
class PipelineConfig:
    """Runtime configuration for the newsletter pipeline."""

    zips_dir: Path
    newsletters_dir: Path
    media_dir: Path
    model: str
    timezone: tzinfo
    llm: LLMConfig
    enrichment: EnrichmentConfig
    cache: CacheConfig
    anonymization: AnonymizationConfig
    rag: RAGConfig

    # Virtual groups (merges) - main configuration for multi-group processing
    merges: dict[str, MergeConfig] = field(default_factory=dict)

    # If True, skip real groups that are part of virtual groups
    skip_real_if_in_virtual: bool = True

    @classmethod
    def with_defaults(
        cls,
        *,
        zips_dir: Path | None = None,
        newsletters_dir: Path | None = None,
        media_dir: Path | None = None,
        model: str | None = None,
        timezone: tzinfo | None = None,
        llm: LLMConfig | None = None,
        enrichment: EnrichmentConfig | None = None,
        cache: CacheConfig | None = None,
        anonymization: AnonymizationConfig | None = None,
        rag: RAGConfig | None = None,
        merges: dict[str, MergeConfig] | None = None,
        skip_real_if_in_virtual: bool = True,
    ) -> "PipelineConfig":
        """Create a configuration using project defaults."""

        return cls(
            zips_dir=_ensure_safe_directory(zips_dir or Path("data/whatsapp_zips")),
            newsletters_dir=_ensure_safe_directory(
                newsletters_dir or Path("data/daily")
            ),
            media_dir=_ensure_safe_directory(media_dir or Path("media")),
            model=model or DEFAULT_MODEL,
            timezone=timezone or ZoneInfo(DEFAULT_TIMEZONE),
            llm=(copy.deepcopy(llm) if llm else LLMConfig()),
            enrichment=(
                copy.deepcopy(enrichment) if enrichment else EnrichmentConfig()
            ),
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

        data = _load_toml_data(toml_path)

        # Parse merges
        merges_raw = data.get("merges", {})
        if not isinstance(merges_raw, dict):
            raise ValueError("'merges' section must be a table")

        merges: dict[str, MergeConfig] = {}
        for slug, merge_data in merges_raw.items():
            if not isinstance(merge_data, dict):
                raise ValueError(f"Merge '{slug}' must be a table")
            tag_style = merge_data.get("tag_style", "emoji")
            if tag_style not in _VALID_TAG_STYLES:
                raise ValueError(f"Invalid tag_style '{tag_style}' for merge '{slug}'")

            groups = merge_data.get("groups", [])
            if not isinstance(groups, list) or not all(
                isinstance(g, str) for g in groups
            ):
                raise ValueError(f"Merge '{slug}' groups must be a list of strings")
            if not groups:
                raise ValueError(
                    f"Merge '{slug}' must include at least one source group"
                )

            merges[slug] = MergeConfig(
                name=merge_data["name"],
                source_groups=groups,
                tag_style=tag_style,
                group_emojis=merge_data.get("emojis", {}),
                model_override=merge_data.get("model"),
            )

        # Parse directories
        dirs = data.get("directories", {})
        pipeline = data.get("pipeline", {})
        if not isinstance(dirs, dict):
            raise ValueError("'directories' section must be a table")
        if not isinstance(pipeline, dict):
            raise ValueError("'pipeline' section must be a table")

        return cls(
            zips_dir=_ensure_safe_directory(dirs.get("zips_dir", "data/whatsapp_zips")),
            newsletters_dir=_ensure_safe_directory(
                dirs.get("newsletters_dir", "data/daily")
            ),
            media_dir=_ensure_safe_directory(dirs.get("media_dir", "media")),
            model=pipeline.get("model", DEFAULT_MODEL),
            timezone=ZoneInfo(pipeline.get("timezone", DEFAULT_TIMEZONE)),
            llm=LLMConfig(**data.get("llm", {})),
            enrichment=EnrichmentConfig(**data.get("enrichment", {})),
            cache=CacheConfig(**data.get("cache", {})),
            anonymization=AnonymizationConfig(**data.get("anonymization", {})),
            rag=RAGConfig(**data.get("rag", {})),
            merges=merges,
            skip_real_if_in_virtual=pipeline.get("skip_real_if_in_virtual", True),
        )


def _ensure_safe_directory(path_value: Any) -> Path:
    """Validate and normalise directory paths loaded from configuration."""

    if isinstance(path_value, Path):
        candidate = path_value.expanduser()
    else:
        candidate = Path(str(path_value)).expanduser()

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
    except ValueError:  # pragma: no cover - defensive on Path API differences
        raise ValueError(
            f"Directory path '{candidate}' must reside within the project directory"
        )

    return resolved


_MAX_TOML_BYTES = 512 * 1024  # 512KB should be plenty for configuration files


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
    # Removed DEFAULT_GROUP_NAME - groups are auto-discovered
    "DEFAULT_MODEL",
    "DEFAULT_TIMEZONE",
    "AnonymizationConfig",
    "CacheConfig",
    "EnrichmentConfig",
    "LLMConfig",
    "PipelineConfig",
    "RAGConfig",
]