import pytest

from egregora.input_adapters.exceptions import UnknownAdapterError
from egregora.input_adapters.registry import InputAdapterRegistry


def test_registry_raises_unknown_adapter_error():
    registry = InputAdapterRegistry()
    # We expect UnknownAdapterError, but currently it raises KeyError
    with pytest.raises(UnknownAdapterError) as exc:
        registry.get("nonexistent_adapter_source")

    assert "nonexistent_adapter_source" in str(exc.value)
