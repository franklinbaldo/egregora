"""Source adapters for different chat platforms.

This package contains adapter implementations for various chat platforms,
converting their specific export formats into the standardized IR schema.

Available Adapters:
- WhatsAppAdapter: For WhatsApp ZIP exports (production-ready)
- SlackAdapter: For Slack exports (stub/template for demonstration)

Plugin System:
- InputAdapterRegistry: Automatically discovers and loads adapters
- get_global_registry(): Access the global adapter registry

Example:
    >>> from egregora.input_adapters import get_global_registry
    >>> registry = get_global_registry()
    >>> adapter = registry.get("whatsapp")
"""
from egregora.input_adapters.base import InputAdapter
from egregora.input_adapters.registry import InputAdapterRegistry, get_global_registry
from egregora.input_adapters.slack import SlackAdapter
from egregora.input_adapters.whatsapp import WhatsAppAdapter

# Legacy registry (deprecated in favor of InputAdapterRegistry)
ADAPTER_REGISTRY: dict[str, type] = {"whatsapp": WhatsAppAdapter, "slack": SlackAdapter}


def get_adapter(source_identifier: str) -> InputAdapter:
    """Get an adapter instance by source identifier.

    Deprecated: Use get_global_registry().get() instead.

    Args:
        source_identifier: Source identifier (e.g., "whatsapp", "slack")

    Returns:
        Adapter instance

    Raises:
        KeyError: If source identifier is not recognized

    Example:
        >>> # New way (recommended)
        >>> from egregora.input_adapters import get_global_registry
        >>> adapter = get_global_registry().get("whatsapp")
        >>>
        >>> # Old way (still works)
        >>> from egregora.input_adapters import get_adapter
        >>> adapter = get_adapter("whatsapp")

    """
    return get_global_registry().get(source_identifier)


def list_adapters() -> list[str]:
    """List all registered adapter identifiers.

    Returns:
        List of adapter source identifiers (e.g., ["whatsapp", "slack"])

    Example:
        >>> from egregora.input_adapters import list_adapters
        >>> adapters = list_adapters()
        >>> print(adapters)
        ['whatsapp', 'slack']

    """
    registry = get_global_registry()
    return list(registry._adapters.keys())


__all__ = [
    "InputAdapterRegistry",
    "SlackAdapter",
    "WhatsAppAdapter",
    "get_adapter",
    "get_global_registry",
    "list_adapters",
]
