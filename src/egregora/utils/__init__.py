"""Utility modules for Egregora.

MODERN (Phase 3): Added consolidated date/time and filesystem utilities.
"""

from egregora.utils.batch import (
    BatchPromptRequest,
    BatchPromptResult,
    EmbeddingBatchRequest,
    EmbeddingBatchResult,
    chunk_requests,
)
from egregora.utils.cache import ENRICHMENT_CACHE_VERSION, EnrichmentCache, make_enrichment_cache_key
from egregora.utils.network import SSRFValidationError, validate_public_url
from egregora.utils.paths import PathTraversalError, ensure_dir, safe_path_join, slugify
from egregora.utils.zip import (
    ZipValidationError,
    ZipValidationSettings,
    configure_default_limits,
    ensure_safe_member_size,
    validate_zip_contents,
)

__all__ = [
    "ENRICHMENT_CACHE_VERSION",
    "BatchPromptRequest",
    "BatchPromptResult",
    "EmbeddingBatchRequest",
    "EmbeddingBatchResult",
    "SSRFValidationError",
    "EnrichmentCache",
    "PathTraversalError",
    "ZipValidationError",
    "ZipValidationSettings",
    "chunk_requests",
    "configure_default_limits",
    "ensure_dir",
    "ensure_safe_member_size",
    "make_enrichment_cache_key",
    "validate_public_url",
    "safe_path_join",
    "slugify",
    "validate_zip_contents",
]
