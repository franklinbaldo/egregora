"""Types for enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend

    from egregora.input_adapters.base import MediaMapping
    from egregora.llm.usage import UsageTracker
    from egregora.orchestration.cache import EnrichmentCache


class EnrichmentOutput(BaseModel):
    """Structured output for enrichment agents."""

    slug: str
    markdown: str
    title: str | None = None
    tags: list[str] = []


@dataclass(frozen=True, slots=True)
class EnrichmentRuntimeContext:
    """Runtime context for enrichment execution."""

    cache: EnrichmentCache
    output_sink: Any
    site_root: Path | None = None
    duckdb_connection: DuckDBBackend | None = None
    target_table: str | None = None
    usage_tracker: UsageTracker | None = None
    pii_prevention: dict[str, Any] | None = None  # LLM-native PII prevention settings
    task_store: Any | None = None  # Added for job queue scheduling


@dataclass
class MediaEnrichmentConfig:
    """Config for media enrichment enqueueing."""

    media_mapping: MediaMapping
    max_enrichments: int
    enable_media: bool
