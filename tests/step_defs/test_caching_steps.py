import json
import shutil
import tempfile
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from egregora.orchestration.cache import CacheTier, PipelineCache, make_enrichment_cache_key
from egregora.orchestration.exceptions import (
    CacheDeserializationError,
    CachePayloadTypeError,
)


# Scenarios

@scenario("../features/caching.feature", "Enrichment cache persistence")
def test_enrichment_cache_persistence():
    pass


@scenario("../features/caching.feature", "Writer cache persistence")
def test_writer_cache_persistence():
    pass


@scenario("../features/caching.feature", "RAG cache persistence")
def test_rag_cache_persistence():
    pass


@scenario("../features/caching.feature", "Force refresh configuration")
def test_force_refresh_configuration():
    pass


@scenario("../features/caching.feature", "Handling deserialization errors")
def test_handling_deserialization_errors():
    pass


@scenario("../features/caching.feature", "Handling invalid payload types")
def test_handling_invalid_payload_types():
    pass


# Fixtures

@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for the cache."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def context():
    """Provides a dictionary for sharing state between steps."""
    return {}


# Given Steps

@given("a clean cache directory", target_fixture="cache_dir")
def clean_cache_directory(temp_cache_dir):
    return temp_cache_dir


@given("an enrichment cache instance", target_fixture="cache")
def enrichment_cache_instance(cache_dir):
    return PipelineCache(cache_dir)


@given("a writer cache instance", target_fixture="cache")
def writer_cache_instance(cache_dir):
    return PipelineCache(cache_dir)


@given("a RAG cache instance", target_fixture="cache")
def rag_cache_instance(cache_dir):
    return PipelineCache(cache_dir)


@given("a cache instance with existing data", target_fixture="cache")
def cache_with_data(cache_dir):
    cache = PipelineCache(cache_dir)
    key = "test-key"
    cache.writer.set(key, "old-value")
    cache.close()
    return cache  # Note: This instance is closed, scenarios will re-open


@given(parsers.parse('a corrupted cache entry for key "{key}"'))
def corrupted_cache_entry(cache, key, mocker):
    # Mock the backend's get method to simulate a JSON decoding error
    mocker.patch.object(
        cache.enrichment.backend,
        "get",
        side_effect=json.JSONDecodeError("mock error", "", 0),
    )


@given(parsers.parse('an invalid payload stored for key "{key}"'))
def invalid_payload_stored(cache, key):
    # Store a non-dictionary value
    cache.enrichment.backend.set(key, "this is a string, not a dict")


# When Steps

@when(parsers.parse('I store an enrichment payload "{payload}" for key "{key}"'))
def store_enrichment_payload(cache, payload, key):
    # We construct a full payload object as per the original test
    full_payload = {"markdown": payload, "slug": "cached-slug", "type": "url"}
    real_key = make_enrichment_cache_key(kind="url", identifier=key)
    cache.enrichment.store(real_key, full_payload)


@when(parsers.parse('I store a writer result for signature "{signature}"'))
def store_writer_result(cache, signature):
    result = {"posts": ["post1"], "profiles": ["profile1"]}
    cache.writer.set(signature, result)


@when(parsers.parse('I store a RAG value for key "{key}"'))
def store_rag_value(cache, key):
    value = {"embeddings": [0.1, 0.2, 0.3], "metadata": {"source": "test.txt"}}
    cache.rag.set(key, value)


@when("I close the cache")
def close_cache(cache):
    cache.close()


@when("I open a new cache instance", target_fixture="new_cache")
def open_new_cache(cache_dir):
    return PipelineCache(cache_dir)


@when(parsers.parse('I initialize a cache with refresh_tiers set to "{tier}"'), target_fixture="refresh_cache")
def init_cache_refresh(cache_dir, tier):
    refresh_set = {tier} if tier != "all" else {"all"}
    return PipelineCache(cache_dir, refresh_tiers=refresh_set)


@when(parsers.parse('I attempt to load the key "{key}"'), target_fixture="error_context")
def attempt_load_key(cache, key, mocker):
    # Spy on the delete method to ensure it's called
    delete_spy = mocker.spy(cache.enrichment.backend, "delete")

    error = None
    try:
        cache.enrichment.load(key)
    except Exception as e:
        error = e

    return {"error": error, "delete_spy": delete_spy}


# Then Steps

@then(parsers.parse('loading the key "{key}" should return the payload "{expected_payload}"'))
def check_enrichment_payload(new_cache, key, expected_payload):
    real_key = make_enrichment_cache_key(kind="url", identifier=key)
    loaded = new_cache.enrichment.load(real_key)
    assert loaded is not None
    assert loaded["markdown"] == expected_payload
    new_cache.close()


@then(parsers.parse('retrieving the signature "{signature}" should return the result'))
def check_writer_result(new_cache, signature):
    loaded = new_cache.writer.get(signature)
    assert loaded is not None
    assert loaded["posts"] == ["post1"]
    new_cache.close()


@then(parsers.parse('retrieving the RAG key "{key}" should return the value'))
def check_rag_result(new_cache, key):
    loaded = new_cache.rag.get(key)
    assert loaded is not None
    assert loaded["embeddings"] == [0.1, 0.2, 0.3]
    new_cache.close()


@then(parsers.parse('it should indicate refresh needed for "{tier_name}" tier'))
def check_refresh_needed(refresh_cache, tier_name):
    tier = getattr(CacheTier, tier_name)
    assert refresh_cache.should_refresh(tier)


@then(parsers.parse('it should not indicate refresh needed for "{tier_name}" tier'))
def check_refresh_not_needed(refresh_cache, tier_name):
    tier = getattr(CacheTier, tier_name)
    assert not refresh_cache.should_refresh(tier)


@then("a CacheDeserializationError should be raised")
def check_deserialization_error(error_context):
    assert isinstance(error_context["error"], CacheDeserializationError)


@then("a CachePayloadTypeError should be raised")
def check_payload_type_error(error_context):
    assert isinstance(error_context["error"], CachePayloadTypeError)


@then(parsers.parse('the key "{key}" should be deleted from the backend'))
def check_key_deleted(error_context, key):
    error_context["delete_spy"].assert_called_once_with(key)
