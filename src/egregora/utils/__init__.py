"""Utility modules for Egregora."""

from .batch import (
    BatchPromptRequest,
    BatchPromptResult,
    EmbeddingBatchRequest,
    EmbeddingBatchResult,
    GeminiBatchClient,
    chunk_requests,
)
from .batching import (
    batch_table,
    batch_table_to_records,
)
from .cache import (
    ENRICHMENT_CACHE_VERSION,
    EnrichmentCache,
    make_enrichment_cache_key,
)
from .checkpoints import (
    DEFAULT_STEP_ORDER,
    CheckpointStore,
)
from .genai import (
    call_with_retries,
    call_with_retries_sync,
    extract_retry_delay,
    is_rate_limit_error,
    sleep_with_progress_sync,
)
from .normalization import (
    ensure_schema_compliance,
    normalize_timestamps,
)
from .paths import (
    PathTraversalError,
    safe_path_join,
    slugify,
)
from .zip import (
    ZipValidationError,
    ZipValidationLimits,
    configure_default_limits,
    ensure_safe_member_size,
    validate_zip_contents,
)

__all__ = [
    # Batch API
    "BatchPromptRequest",
    "BatchPromptResult",
    "EmbeddingBatchRequest",
    "EmbeddingBatchResult",
    "GeminiBatchClient",
    "chunk_requests",
    # Batching utilities
    "batch_table",
    "batch_table_to_records",
    # Cache
    "EnrichmentCache",
    "make_enrichment_cache_key",
    "ENRICHMENT_CACHE_VERSION",
    # Checkpoints
    "CheckpointStore",
    "DEFAULT_STEP_ORDER",
    # GenAI utilities
    "call_with_retries",
    "call_with_retries_sync",
    "is_rate_limit_error",
    "extract_retry_delay",
    "sleep_with_progress_sync",
    # Normalization utilities
    "normalize_timestamps",
    "ensure_schema_compliance",
    # ZIP validation
    "ZipValidationError",
    "ZipValidationLimits",
    "configure_default_limits",
    "validate_zip_contents",
    "ensure_safe_member_size",
    # Path safety
    "PathTraversalError",
    "slugify",
    "safe_path_join",
]
