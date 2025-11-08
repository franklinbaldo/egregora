"""Adapter plugin registry for loading built-in and third-party adapters.

This module provides the AdapterRegistry class which:
- Automatically discovers adapters via Python entry points
- Validates IR version compatibility
- Provides adapter lookup by source identifier
- Enables third-party adapter plugins

Third-party adapters can register via entry points in pyproject.toml:

    [project.entry-points."egregora.adapters"]
    my_adapter = "my_package.adapters:MyAdapter"

"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.pipeline.adapters import SourceAdapter

logger = logging.getLogger(__name__)
__all__ = ["AdapterRegistry", "get_global_registry"]


class AdapterRegistry:
    """Registry for discovering and managing source adapters.

    The registry automatically loads:
    1. Built-in adapters (WhatsApp, Slack stub)
    2. Third-party adapters via entry points (group: 'egregora.adapters')

    Adapters must:
    - Implement SourceAdapter protocol
    - Provide adapter_meta() with ir_version='v1'
    - Be instantiable without arguments

    Example:
        >>> registry = AdapterRegistry()
        >>> adapter = registry.get("whatsapp")
        >>> meta = adapter.adapter_meta()
        >>> print(f"Loaded: {meta['name']} v{meta['version']}")

    """

    def __init__(self) -> None:
        """Initialize registry and load adapters."""
        self._adapters: dict[str, SourceAdapter] = {}
        self._load_builtin()
        self._load_plugins()

    def _load_builtin(self) -> None:
        """Load built-in adapters (WhatsApp, Slack)."""
        try:
            from egregora.adapters.whatsapp import WhatsAppAdapter

            adapter = WhatsAppAdapter()
            meta = adapter.adapter_meta()
            self._adapters[meta["source"]] = adapter
            logger.debug("Loaded built-in adapter: %s v%s", meta["name"], meta["version"])
        except Exception:
            logger.exception("Failed to load WhatsAppAdapter")

        try:
            from egregora.adapters.slack import SlackAdapter

            adapter = SlackAdapter()
            meta = adapter.adapter_meta()
            self._adapters[meta["source"]] = adapter
            logger.debug("Loaded built-in adapter: %s v%s", meta["name"], meta["version"])
        except Exception:
            logger.exception("Failed to load SlackAdapter")

    def _load_plugins(self) -> None:
        """Load third-party adapters from entry points.

        Entry points should be registered under group 'egregora.adapters'.
        Each entry point should provide a SourceAdapter class.

        """
        discovered = entry_points(group="egregora.adapters")

        for ep in discovered:
            try:
                # Load adapter class from entry point
                adapter_cls = ep.load()
                adapter = adapter_cls()

                # Validate adapter protocol
                if not hasattr(adapter, "adapter_meta"):
                    logger.warning(
                        "Plugin %s does not implement adapter_meta(), skipping",
                        ep.name,
                    )
                    continue

                meta = adapter.adapter_meta()

                # Validate IR version
                if meta["ir_version"] != "v1":
                    logger.warning(
                        "Adapter %s requires IR %s (current: v1), skipping",
                        ep.name,
                        meta["ir_version"],
                    )
                    continue

                # Register adapter
                self._adapters[meta["source"]] = adapter
                logger.info("Loaded plugin adapter: %s v%s (from %s)", meta["name"], meta["version"], ep.name)

            except Exception:
                logger.exception("Failed to load plugin adapter: %s", ep.name)

    def get(self, source_identifier: str) -> SourceAdapter:
        """Get adapter by source identifier.

        Args:
            source_identifier: Source identifier (e.g., "whatsapp", "slack")

        Returns:
            Adapter instance

        Raises:
            KeyError: If source identifier not found

        Example:
            >>> registry = AdapterRegistry()
            >>> adapter = registry.get("whatsapp")
            >>> table = adapter.parse(Path("export.zip"))

        """
        if source_identifier not in self._adapters:
            available = ", ".join(self._adapters.keys())
            msg = f"Unknown source: '{source_identifier}'. Available: {available}"
            raise KeyError(msg)
        return self._adapters[source_identifier]

    def list_adapters(self) -> list[dict[str, str]]:
        """List all registered adapters with metadata.

        Returns:
            List of adapter metadata dictionaries

        Example:
            >>> registry = AdapterRegistry()
            >>> for meta in registry.list_adapters():
            ...     print(f"{meta['name']} v{meta['version']}")

        """
        return [adapter.adapter_meta() for adapter in self._adapters.values()]

    def __contains__(self, source_identifier: str) -> bool:
        """Check if source identifier is registered."""
        return source_identifier in self._adapters

    def __len__(self) -> int:
        """Return number of registered adapters."""
        return len(self._adapters)

    def __repr__(self) -> str:
        """String representation of registry."""
        count = len(self._adapters)
        sources = ", ".join(self._adapters.keys())
        return f"AdapterRegistry(adapters={count}, sources=[{sources}])"


# Global registry instance (lazy-loaded)
_global_registry: AdapterRegistry | None = None


def get_global_registry() -> AdapterRegistry:
    """Get the global adapter registry (singleton pattern).

    This provides a convenient way to access adapters without
    creating multiple registry instances.

    Returns:
        Global AdapterRegistry instance

    Example:
        >>> from egregora.adapters.registry import get_global_registry
        >>> registry = get_global_registry()
        >>> adapter = registry.get("whatsapp")

    """
    global _global_registry  # noqa: PLW0603
    if _global_registry is None:
        _global_registry = AdapterRegistry()
    return _global_registry
