from __future__ import annotations

from unittest.mock import Mock

import pytest

from egregora.utils.cache import EnrichmentCache
from egregora.utils.exceptions import CachePayloadTypeError


def test_enrichment_cache_load_raises_on_invalid_payload_type() -> None:
    """Test that EnrichmentCache.load raises CachePayloadTypeError for non-dict payloads."""
    # Arrange
    mock_backend = Mock()
    key = "test_key"
    invalid_payload = ["this", "is", "a", "list"]
    mock_backend.get.return_value = invalid_payload

    cache = EnrichmentCache(backend=mock_backend)

    # Act & Assert
    with pytest.raises(CachePayloadTypeError) as excinfo:
        cache.load(key)

    # Assert that the exception has the correct context
    assert excinfo.value.key == key
    assert excinfo.value.payload_type is type(invalid_payload)
    mock_backend.delete.assert_called_once_with(key)
