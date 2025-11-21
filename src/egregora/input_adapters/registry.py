"""Adapter plugin registry for loading built-in and third-party adapters.

This module provides the InputAdapterRegistry class which:
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
    from egregora.input_adapters.base import InputAdapter

logger = logging.getLogger(__name__)
__all__ = ["InputAdapterRegistry", "get_global_registry"]


class InputAdapterRegistry:
    """Registry for discovering and managing source adapters.

    The registry automatically loads:
    1. Built-in adapters (WhatsApp)
    2. Third-party adapters via entry points (group: 'egregora.adapters')

    Adapters must:
    - Implement InputAdapter protocol
    - Provide get_adapter_metadata() with ir_version='v1'
    - Be instantiable without arguments

    Example:
        >>> registry = InputAdapterRegistry()
        >>> adapter = registry.get("whatsapp")
        >>> table = adapter.parse(Path("export.zip"))

    """

    def __init__(self) -> None:
        """Initialize registry and load adapters."""
        self._adapters: dict[str, InputAdapter] = {}
        self._load_builtin()
        self._load_plugins()

    def _load_builtin(self) -> None:
        """Load built-in adapters (WhatsApp)."""
        try:
            from egregora.input_adapters.whatsapp import WhatsAppAdapter

            adapter = WhatsAppAdapter()
            meta = adapter.get_adapter_metadata()
            self._adapters[meta["source"]] = adapter
            logger.debug("Loaded built-in adapter: %s v%s", meta["name"], meta["version"])
        except Exception:
            logger.exception("Failed to load WhatsAppAdapter")

    def _load_plugins(self) -> None:
        """Load third-party adapters from entry points.

        Entry points should be registered under group 'egregora.adapters'.
        Each entry point should provide a InputAdapter class.

        """
        discovered = entry_points(group="egregora.adapters")

        for ep in discovered:
            try:
                # Load adapter class from entry point
                adapter_cls = ep.load()
                adapter = adapter_cls()

                # Validate adapter protocol
                if not hasattr(adapter, "get_adapter_metadata"):
                    logger.warning(
                        "Plugin %s does not implement get_adapter_metadata(), skipping",
                        ep.name,
                    )
                    continue

                meta = adapter.get_adapter_metadata()

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

    def get(self, source_identifier: str) -> InputAdapter:
        """Get adapter by source identifier.

        Args:
            source_identifier: Source identifier (e.g., "whatsapp")

        Returns:
            Adapter instance

        Raises:
            KeyError: If source identifier not found

        Example:
            >>> registry = InputAdapterRegistry()
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
            >>> registry = InputAdapterRegistry()
            >>> for meta in registry.list_adapters():
            ...     print(f"{meta['name']} v{meta['version']}")

        """
        return [adapter.get_adapter_metadata() for adapter in self._adapters.values()]

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
        return f"InputAdapterRegistry(adapters={count}, sources=[{sources}])"


# Global registry instance (lazy-loaded)
_global_registry: InputAdapterRegistry | None = None


def get_global_registry() -> InputAdapterRegistry:
    """Get the global adapter registry (singleton pattern).

    This provides a convenient way to access adapters without
    creating multiple registry instances.

    Returns:
        Global InputAdapterRegistry instance

    Example:
        >>> from egregora.input_adapters.registry import get_global_registry
        >>> registry = get_global_registry()
        >>> adapter = registry.get("whatsapp")

    """
    global _global_registry  # noqa: PLW0603
    if _global_registry is None:
        _global_registry = InputAdapterRegistry()
    return _global_registry
