"""Utility modules for Egregora."""

from egregora.utils.batch import (
    BatchPromptRequest,
    BatchPromptResult,
    EmbeddingBatchRequest,
    EmbeddingBatchResult,
    GeminiBatchClient,
    chunk_requests,
)
from egregora.utils.cache import (
    ENRICHMENT_CACHE_VERSION,
    EnrichmentCache,
    make_enrichment_cache_key,
)
from egregora.utils.checkpoints import DEFAULT_STEP_ORDER, CheckpointStore
from egregora.utils.genai import (
    call_with_retries,
    call_with_retries_sync,
    extract_retry_delay,
    is_rate_limit_error,
    sleep_with_progress_sync,
)
from egregora.utils.paths import PathTraversalError, safe_path_join, slugify
from egregora.utils.zip import (
    ZipValidationError,
    ZipValidationLimits,
    configure_default_limits,
    ensure_safe_member_size,
    validate_zip_contents,
)

__all__ = [
    "DEFAULT_STEP_ORDER",
    "ENRICHMENT_CACHE_VERSION",
    # Batch API
    "BatchPromptRequest",
    "BatchPromptResult",
    # Checkpoints
    "CheckpointStore",
    "EmbeddingBatchRequest",
    "EmbeddingBatchResult",
    # Cache
    "EnrichmentCache",
    "GeminiBatchClient",
    # Path safety
    "PathTraversalError",
    # ZIP validation
    "ZipValidationError",
    "ZipValidationLimits",
    # GenAI utilities
    "call_with_retries",
    "call_with_retries_sync",
    "chunk_requests",
    "configure_default_limits",
    "ensure_safe_member_size",
    "extract_retry_delay",
    "is_rate_limit_error",
    "make_enrichment_cache_key",
    "safe_path_join",
    "sleep_with_progress_sync",
    "slugify",
    "validate_zip_contents",
]
