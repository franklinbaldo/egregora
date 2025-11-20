"""Simple enrichment: extract media, add LLM-described context as table rows.

Enrichment adds context for URLs and media as new table rows with author 'egregora'.
The LLM sees enrichment context inline with original messages.

Documentation:
- Architecture (Enricher): docs/guides/architecture.md#4-enricher-enricherpy
- Core Concepts: docs/getting-started/concepts.md#4-enrich-optional
"""

from egregora.ops.media import (
    detect_media_type,
    extract_media_from_zip,
    extract_urls,
    find_media_references,
    get_media_subfolder,
    replace_media_mentions,
)
from egregora.enrichment.runners import (
    EnrichmentRuntimeContext,
    MediaEnrichmentJob,
    UrlEnrichmentJob,
    build_batch_requests,
    enrich_table,
    map_batch_results,
)

__all__ = [
    "EnrichmentRuntimeContext",
    "MediaEnrichmentJob",
    "UrlEnrichmentJob",
    "build_batch_requests",
    "detect_media_type",
    "enrich_table",
    "extract_media_from_zip",
    "extract_urls",
    "find_media_references",
    "get_media_subfolder",
    "map_batch_results",
    "replace_media_mentions",
]
