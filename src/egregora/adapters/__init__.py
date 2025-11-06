"""Source adapters for different chat platforms.

This package contains adapter implementations for various chat platforms,
converting their specific export formats into the standardized IR schema.

Available Adapters:
- WhatsAppAdapter: For WhatsApp ZIP exports (production-ready)
- SlackAdapter: For Slack exports (stub/template for demonstration)
"""

from egregora.adapters.slack import SlackAdapter
from egregora.adapters.whatsapp import WhatsAppAdapter
from egregora.pipeline.adapters import SourceAdapter

ADAPTER_REGISTRY: dict[str, type] = {"whatsapp": WhatsAppAdapter, "slack": SlackAdapter}


def get_adapter(source_identifier: str) -> SourceAdapter:
    """Get an adapter instance by source identifier.

    Args:
        source_identifier: Source identifier (e.g., "whatsapp", "slack")

    Returns:
        Adapter instance

    Raises:
        ValueError: If source identifier is not recognized

    """
    if source_identifier not in ADAPTER_REGISTRY:
        available = ", ".join(ADAPTER_REGISTRY.keys())
        msg = f"Unknown source: '{source_identifier}'. Available sources: {available}"
        raise ValueError(msg)
    adapter_class = ADAPTER_REGISTRY[source_identifier]
    return adapter_class()


__all__ = ["ADAPTER_REGISTRY", "SlackAdapter", "WhatsAppAdapter", "get_adapter"]
