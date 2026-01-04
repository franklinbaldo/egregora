"""Test legacy compatibility shims to ensure they are importable."""

def test_legacy_authors_imports():
    """Verify that objects from the legacy authors module can be imported."""
    from egregora.utils.authors import AuthorsFileLoadError
    assert AuthorsFileLoadError is not None

def test_legacy_cache_imports():
    """Verify that objects from the legacy cache module can be imported."""
    from egregora.utils.cache import (
        CacheDeserializationError,
        CacheKeyNotFoundError,
        CachePayloadTypeError,
        CacheTier,
        DiskCacheBackend,
        EnrichmentCache,
        PipelineCache,
        make_enrichment_cache_key,
    )
    assert CacheDeserializationError is not None
    assert CacheKeyNotFoundError is not None
    assert CachePayloadTypeError is not None
    assert CacheTier is not None
    assert DiskCacheBackend is not None
    assert EnrichmentCache is not None
    assert PipelineCache is not None
    assert make_enrichment_cache_key is not None

def test_legacy_exceptions_imports():
    """Verify that objects from the legacy exceptions module can be imported."""
    from egregora.utils.exceptions import (
        CacheDeserializationError,
        CacheError,
        CacheKeyNotFoundError,
        CachePayloadTypeError,
        DateTimeParsingError,
        InvalidDateTimeInputError,
    )
    assert CacheDeserializationError is not None
    assert CacheError is not None
    assert CacheKeyNotFoundError is not None
    assert CachePayloadTypeError is not None
    assert DateTimeParsingError is not None
    assert InvalidDateTimeInputError is not None
