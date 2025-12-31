from __future__ import annotations

import pytest

from egregora.utils.cache_backend import DiskCacheBackend
from egregora.utils.exceptions import CacheKeyNotFoundError


def test_disk_cache_backend_get_raises_key_not_found_error(tmp_path):
    """Verify `get` raises CacheKeyNotFoundError for a missing key."""
    backend = DiskCacheBackend(tmp_path)
    with pytest.raises(CacheKeyNotFoundError, match="Key not found in cache: 'missing-key'"):
        backend.get("missing-key")


def test_disk_cache_backend_set_and_get(tmp_path):
    """Verify that a value can be set and then retrieved."""
    backend = DiskCacheBackend(tmp_path)
    backend.set("test-key", "test-value")
    assert backend.get("test-key") == "test-value"


def test_disk_cache_backend_delete(tmp_path):
    """Verify that a value can be deleted."""
    backend = DiskCacheBackend(tmp_path)
    backend.set("test-key", "test-value")
    backend.delete("test-key")
    with pytest.raises(CacheKeyNotFoundError):
        backend.get("test-key")


def test_disk_cache_backend_dunder_methods(tmp_path):
    """Verify that the dunder methods work as expected."""
    backend = DiskCacheBackend(tmp_path)
    backend["test-key"] = "test-value"
    assert backend["test-key"] == "test-value"
    del backend["test-key"]
    with pytest.raises(CacheKeyNotFoundError):
        _ = backend["test-key"]
