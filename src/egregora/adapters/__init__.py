"""Source adapters for different chat platforms.

This package contains adapter implementations for various chat platforms,
converting their specific export formats into the standardized IR schema.

Available Adapters:
- WhatsAppAdapter: For WhatsApp ZIP exports (production-ready)
- SlackAdapter: For Slack exports (stub/template for demonstration)

Plugin System:
- AdapterRegistry: Automatically discovers and loads adapters
- get_global_registry(): Access the global adapter registry

Example:
    >>> from egregora.adapters import get_global_registry
    >>> registry = get_global_registry()
    >>> adapter = registry.get("whatsapp")

"""

from egregora.adapters.registry import AdapterRegistry, get_global_registry
from egregora.adapters.slack import SlackAdapter
from egregora.adapters.whatsapp import WhatsAppAdapter
from egregora.sources.base import SourceAdapter

# Legacy registry (deprecated in favor of AdapterRegistry)
ADAPTER_REGISTRY: dict[str, type] = {"whatsapp": WhatsAppAdapter, "slack": SlackAdapter}


def get_adapter(source_identifier: str) -> SourceAdapter:
    """Get an adapter instance by source identifier.

    DEPRECATED: Use get_global_registry().get() instead.

    Args:
        source_identifier: Source identifier (e.g., "whatsapp", "slack")

    Returns:
        Adapter instance

    Raises:
        KeyError: If source identifier is not recognized

    Example:
        >>> # New way (recommended)
        >>> from egregora.adapters import get_global_registry
        >>> adapter = get_global_registry().get("whatsapp")
        >>>
        >>> # Old way (still works)
        >>> from egregora.adapters import get_adapter
        >>> adapter = get_adapter("whatsapp")

    """
    return get_global_registry().get(source_identifier)


__all__ = [
    "AdapterRegistry",
    "SlackAdapter",
    "WhatsAppAdapter",
    "get_adapter",
    "get_global_registry",
]
