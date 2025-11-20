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
# from egregora.utils.genai import (
#     call_with_retries,
#     call_with_retries_sync,
#     extract_retry_delay,
#     is_rate_limit_error,
#     sleep_with_progress_sync,
# )
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
    "EnrichmentCache",
    "PathTraversalError",
    "ZipValidationError",
    "ZipValidationSettings",
    # "call_with_retries",
    # "call_with_retries_sync",
    "chunk_requests",
    "configure_default_limits",
    "ensure_dir",
    "ensure_safe_member_size",
    # "extract_retry_delay",
    # "is_rate_limit_error",
    "make_enrichment_cache_key",
    "safe_path_join",
    # "sleep_with_progress_sync",
    "slugify",
    "validate_zip_contents",
]
