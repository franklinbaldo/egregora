"""Simple enrichment: extract media, add LLM-described context as table rows.

Enrichment adds context for URLs and media as new table rows with author 'egregora'.
The LLM sees enrichment context inline with original messages.

Documentation:
- Architecture (Enricher): docs/guides/architecture.md#4-enricher-enricherpy
- Core Concepts: docs/getting-started/concepts.md#4-enrich-optional
"""

from .batch import (
    MediaEnrichmentJob,
    UrlEnrichmentJob,
    build_batch_requests,
    map_batch_results,
)
from .core import enrich_table
from .media import (
    detect_media_type,
    extract_and_replace_media,
    extract_media_from_zip,
    extract_urls,
    find_media_references,
    get_media_subfolder,
    replace_media_mentions,
)

__all__ = [
    # Core enrichment
    "enrich_table",
    # Media utilities
    "extract_and_replace_media",
    "extract_media_from_zip",
    "find_media_references",
    "extract_urls",
    "detect_media_type",
    "get_media_subfolder",
    "replace_media_mentions",
    # Batch utilities
    "MediaEnrichmentJob",
    "UrlEnrichmentJob",
    "build_batch_requests",
    "map_batch_results",
]
