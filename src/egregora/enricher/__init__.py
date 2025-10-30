"""Simple enrichment: extract media, add LLM-described context as DataFrame rows.

Enrichment adds context for URLs and media as new DataFrame rows with author 'egregora'.
The LLM sees enrichment context inline with original messages.

Documentation:
- Architecture (Enricher): docs/guides/architecture.md#4-enricher-enricherpy
- Core Concepts: docs/getting-started/concepts.md#4-enrich-optional
"""

from .core import (
    enrich_dataframe,
    extract_and_replace_media,
    extract_media_from_zip,
    detect_media_type,
    extract_urls,
    find_media_references,
    replace_media_mentions,
    get_media_subfolder,
)

__all__ = [
    "enrich_dataframe",
    "extract_and_replace_media",
    "extract_media_from_zip",
    "detect_media_type",
    "extract_urls",
    "find_media_references",
    "replace_media_mentions",
    "get_media_subfolder",
]
