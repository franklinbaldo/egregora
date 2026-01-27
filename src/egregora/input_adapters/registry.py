"""Adapter plugin registry for loading adapters via entry points.

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

import importlib
import logging
from collections.abc import Mapping
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, cast

from egregora.input_adapters.exceptions import AdapterLoadError, UnknownAdapterError

if TYPE_CHECKING:
    from egregora.input_adapters.base import InputAdapter

logger = logging.getLogger(__name__)
__all__ = ["InputAdapterRegistry", "get_global_registry"]


class InputAdapterRegistry:
    """Registry for discovering and managing source adapters.

    The registry automatically loads adapters from the
    'egregora.adapters' entry point group, enabling both built-in and
    third-party adapters to share the same discovery mechanism.

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
        self._load_plugins()

        if not self._adapters:
            logger.info("No adapters discovered via entry points; registering built-in adapters")
            self._register_builtin_adapters()

    def _load_plugins(self) -> None:
        """Load adapters from entry points.

        Entry points should be registered under group 'egregora.adapters'.
        Each entry point should provide an InputAdapter class.

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

            except Exception as e:
                # Wrap in AdapterLoadError for consistent logging structure,
                # though we still swallow it to prevent startup crashes.
                error = AdapterLoadError(ep.name, e)
                logger.exception("Failed to load plugin adapter: %s", error)

    def _register_builtin_adapters(self) -> None:
        """Register adapters bundled with the application.

        This acts as a fallback when entry point discovery is unavailable,
        such as when running from a source checkout without an installed
        distribution. Built-ins are only added when a source identifier has
        not already been registered via plugins.
        """
        # Note: We use dynamic imports to avoid circular dependencies and import overhead
        # for unused adapters. This is an intentional pattern for plugin-like systems.
        builtin_map = {
            "egregora.input_adapters.whatsapp.adapter": "WhatsAppAdapter",
            "egregora.input_adapters.iperon_tjro": "IperonTJROAdapter",
            "egregora.input_adapters.self_reflection": "SelfInputAdapter",
        }

        for module_name, class_name in builtin_map.items():
            try:
                module = importlib.import_module(module_name)
                adapter_cls = getattr(module, class_name)
                adapter = adapter_cls()
                meta = adapter.get_adapter_metadata()

                if meta["source"] in self._adapters:
                    continue

                self._adapters[meta["source"]] = adapter
                logger.info("Registered built-in adapter: %s v%s", meta["name"], meta["version"])
            except Exception as e:
                error = AdapterLoadError(class_name, e)
                logger.exception("Failed to initialize built-in adapter: %s", error)

    def get(self, source_identifier: str) -> InputAdapter:
        """Get adapter by source identifier.

        Args:
            source_identifier: Source identifier (e.g., "whatsapp")

        Returns:
            Adapter instance

        Raises:
            UnknownAdapterError: If source identifier not found

        Example:
            >>> registry = InputAdapterRegistry()
            >>> adapter = registry.get("whatsapp")
            >>> table = adapter.parse(Path("export.zip"))

        """
        if source_identifier not in self._adapters:
            raise UnknownAdapterError(source_identifier, list(self._adapters.keys()))
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
        # Convert TypedDict to plain dict for broader compatibility
        return [
            dict(cast("Mapping[str, str]", adapter.get_adapter_metadata()))
            for adapter in self._adapters.values()
        ]

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
    global _global_registry
    if _global_registry is None:
        _global_registry = InputAdapterRegistry()
    return _global_registry
