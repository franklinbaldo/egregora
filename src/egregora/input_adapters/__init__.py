"""Source adapters for different chat platforms.

This package contains adapter implementations for various chat platforms,
converting their specific export formats into the standardized IR schema.

Available Adapters:
- WhatsAppAdapter: For WhatsApp ZIP exports (production-ready)
- IperonTJROAdapter: For TJRO workflow imports
- SelfInputAdapter: Experimental self-reflection adapter

Adapter Access Patterns:

1. **ADAPTER_REGISTRY** - For stateful adapters requiring custom configuration:
    >>> from egregora.input_adapters import ADAPTER_REGISTRY
    >>> adapter_cls = ADAPTER_REGISTRY["whatsapp"]
    >>> adapter = adapter_cls(config=my_config)  # Pass config at instantiation
    >>> table = adapter.parse(input_path)

2. **InputAdapterRegistry** - For stateless singleton adapters:
    >>> from egregora.input_adapters import get_global_registry
    >>> adapter = get_global_registry().get("whatsapp")  # Pre-instantiated
    >>> table = adapter.parse(input_path)

Note: ADAPTER_REGISTRY is used by the main pipeline for adapters that need
config-based privacy settings. InputAdapterRegistry is used for diagnostics
and simple adapter discovery.

"""

from egregora.input_adapters.base import InputAdapter
from egregora.input_adapters.iperon_tjro import IperonTJROAdapter
from egregora.input_adapters.registry import InputAdapterRegistry, get_global_registry
from egregora.input_adapters.self_reflection import SelfInputAdapter
from egregora.input_adapters.whatsapp.adapter import WhatsAppAdapter

# Adapter class registry for stateful adapter instantiation
# Note: InputAdapterRegistry creates singleton instances, but adapters like WhatsApp
# need config at instantiation time. This registry provides adapter classes for
# manual instantiation with custom configuration.
ADAPTER_REGISTRY: dict[str, type] = {
    "whatsapp": WhatsAppAdapter,
    "iperon-tjro": IperonTJROAdapter,
    "self": SelfInputAdapter,
}




def list_adapters() -> list[str]:
    """List all registered adapter identifiers.

    Returns:
        List of adapter source identifiers (e.g., ["whatsapp"])

    Example:
        >>> from egregora.input_adapters import list_adapters
        >>> adapters = list_adapters()
        >>> print(adapters)
        ['whatsapp']

    """
    registry = get_global_registry()
    return list(registry._adapters.keys())


__all__ = [
    "ADAPTER_REGISTRY",
    "InputAdapter",
    "InputAdapterRegistry",
    "IperonTJROAdapter",
    "SelfInputAdapter",
    "WhatsAppAdapter",
    "get_global_registry",
    "list_adapters",
]
