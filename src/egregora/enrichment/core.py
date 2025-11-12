"""Simple enrichment: extract media, add LLM-described context as table rows.

Enrichment adds context for URLs and media as new table rows with author 'egregora'.
The LLM sees enrichment context inline with original messages.

Documentation:
- Architecture (Enricher): docs/guides/architecture.md#4-enricher-enricherpy
- Core Concepts: docs/getting-started/concepts.md#4-enrich-optional

MODERN (Phase 2): Uses EnrichmentRuntimeContext to reduce parameters.

MODERN (Phase 11 - Thin-agent pattern): Simplified to use thin agents with straight-loop logic.
No batching, no job orchestration. One agent call per item, cache hits skip API calls.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ibis.expr.types import Table

from egregora.config.settings import EgregoraConfig
from egregora.enrichment.simple_runner import enrich_table_simple

if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend

    from egregora.utils.cache import EnrichmentCache
else:
    DuckDBBackend = Any
    EnrichmentCache = Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EnrichmentRuntimeContext:
    """Runtime context for enrichment execution.

    MODERN (Phase 2): Bundles runtime parameters to reduce function signatures.
    Separates runtime data (paths, cache, DB) from configuration (EgregoraConfig).
    """

    cache: EnrichmentCache
    docs_dir: Path
    posts_dir: Path
    output_format: Any  # OutputFormat - storage protocol coordinator
    site_root: Path | None = None  # For custom prompt overrides in {site_root}/.egregora/prompts/
    duckdb_connection: "DuckDBBackend | None" = None
    target_table: str | None = None


def enrich_table(
    messages_table: Table,
    media_mapping: dict[str, Path],
    config: EgregoraConfig,
    context: EnrichmentRuntimeContext,
) -> Table:
    """Add LLM-generated enrichment rows to Table for URLs and media.

    MODERN (Phase 2): Reduced from 13 parameters to 4 (table, media_mapping, config, context).
    MODERN (Phase 11 - Thin-agent pattern): Delegated to enrich_table_simple for straightforward logic.

    Args:
        messages_table: Table with messages to enrich
        media_mapping: Mapping of media filenames to file paths
        config: Egregora configuration (models, enrichment settings)
        context: Runtime context (cache, paths, DB connection)

    Returns:
        Table with enrichment rows added

    """
    # Delegate to simple runner (thin-agent pattern)
    return enrich_table_simple(
        messages_table=messages_table,
        media_mapping=media_mapping,
        config=config,
        context=context,
    )
