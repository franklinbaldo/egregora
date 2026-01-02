from egregora.agents.shared.cache import make_enrichment_cache_key


def test_make_enrichment_cache_key_stability():
    """Test that the cache key is stable for the same inputs."""
    key1 = make_enrichment_cache_key(kind="url", identifier="http://example.com")
    key2 = make_enrichment_cache_key(kind="url", identifier="http://example.com")
    assert key1 == key2


def test_make_enrichment_cache_key_uniqueness():
    """Test that the cache key is unique for different inputs."""
    key1 = make_enrichment_cache_key(kind="url", identifier="http://example.com")
    key2 = make_enrichment_cache_key(kind="media", identifier="http://example.com")
    key3 = make_enrichment_cache_key(kind="url", identifier="http://example.org")
    assert key1 != key2
    assert key1 != key3
    assert key2 != key3


def test_make_enrichment_cache_key_versioning():
    """Test that the cache key changes with the version."""
    key1 = make_enrichment_cache_key(kind="url", identifier="http://example.com", version="v1")
    key2 = make_enrichment_cache_key(kind="url", identifier="http://example.com", version="v2")
    assert key1 != key2


def test_make_enrichment_cache_key_default_version():
    """Test that the function uses the default version."""
    from egregora.agents.shared.cache import ENRICHMENT_CACHE_VERSION

    key1 = make_enrichment_cache_key(kind="url", identifier="http://example.com")
    key2 = make_enrichment_cache_key(
        kind="url", identifier="http://example.com", version=ENRICHMENT_CACHE_VERSION
    )
    assert key1 == key2
