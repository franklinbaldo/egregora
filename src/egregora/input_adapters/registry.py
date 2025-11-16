"""Adapter plugin registry for loading built-in and third-party adapters.

This module provides the InputAdapterRegistry class which:
- Automatically discovers adapters via Python entry points
- Validates IR version compatibility
- Optionally validates adapter outputs against IR v1 schema
- Provides adapter lookup by source identifier
- Enables third-party adapter plugins

Third-party adapters can register via entry points in pyproject.toml:

    [project.entry-points."egregora.adapters"]
    my_adapter = "my_package.adapters:MyAdapter"

"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.input_adapters.base import InputAdapter

logger = logging.getLogger(__name__)
__all__ = ["InputAdapterRegistry", "get_global_registry"]


class ValidatedAdapter:
    """Wrapper that validates adapter outputs against IR v1 schema.

    This wrapper intercepts the parse() method and automatically validates
    its output before returning to the caller.

    Args:
        adapter: Source adapter to wrap
        validate: Whether to enable validation (default: True)

    Example:
        >>> adapter = WhatsAppAdapter()
        >>> validated = ValidatedAdapter(adapter)
        >>> table = validated.parse(Path("export.zip"))  # Auto-validated

    """

    def __init__(self, adapter: InputAdapter, *, validate: bool = True) -> None:
        """Initialize validated adapter wrapper."""
        self._adapter = adapter
        self._validate = validate

    def parse(self, input_path: Path, **kwargs: Any) -> Table:
        """Parse and validate adapter output.

        Args:
            input_path: Path to source export
            **kwargs: Additional arguments for adapter

        Returns:
            Validated Ibis table

        Raises:
            SchemaError: If validation enabled and output invalid

        """
        # Call original parse method
        result = self._adapter.parse(input_path, **kwargs)

        # Validate if enabled
        if self._validate:
            from egregora.database.validation import adapter_output_validator

            result = adapter_output_validator(result)
            logger.debug("Validated %s adapter output", self._adapter.source_identifier)

        return result

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to wrapped adapter."""
        return getattr(self._adapter, name)

    def __repr__(self) -> str:
        """String representation."""
        return f"ValidatedAdapter({self._adapter!r}, validate={self._validate})"


class InputAdapterRegistry:
    """Registry for discovering and managing source adapters.

    The registry automatically loads:
    1. Built-in adapters (WhatsApp, Slack stub)
    2. Third-party adapters via entry points (group: 'egregora.adapters')

    Adapters must:
    - Implement InputAdapter protocol
    - Provide get_adapter_metadata() with ir_version='v1'
    - Be instantiable without arguments

    Args:
        validate_outputs: If True, wrap adapters to auto-validate outputs (default: False)

    Example:
        >>> # Without validation
        >>> registry = InputAdapterRegistry()
        >>> adapter = registry.get("whatsapp")
        >>>
        >>> # With auto-validation
        >>> registry = InputAdapterRegistry(validate_outputs=True)
        >>> adapter = registry.get("whatsapp")
        >>> table = adapter.parse(Path("export.zip"))  # Auto-validated

    """

    def __init__(self, *, validate_outputs: bool = False) -> None:
        """Initialize registry and load adapters.

        Args:
            validate_outputs: If True, wrap adapters to auto-validate IR v1 schema

        """
        self._adapters: dict[str, InputAdapter] = {}
        self._validate_outputs = validate_outputs
        self._load_builtin()
        self._load_plugins()

    def _load_builtin(self) -> None:
        """Load built-in adapters (WhatsApp, Slack)."""
        try:
            from egregora.input_adapters.whatsapp import WhatsAppAdapter

            adapter = WhatsAppAdapter()
            meta = adapter.get_adapter_metadata()

            # Wrap with validation if enabled
            if self._validate_outputs:
                adapter = ValidatedAdapter(adapter)  # type: ignore[assignment]

            self._adapters[meta["source"]] = adapter
            logger.debug("Loaded built-in adapter: %s v%s", meta["name"], meta["version"])
        except Exception:
            logger.exception("Failed to load WhatsAppAdapter")

        try:
            from egregora.input_adapters.slack import SlackAdapter

            adapter = SlackAdapter()
            meta = adapter.get_adapter_metadata()

            # Wrap with validation if enabled
            if self._validate_outputs:
                adapter = ValidatedAdapter(adapter)  # type: ignore[assignment]

            self._adapters[meta["source"]] = adapter
            logger.debug("Loaded built-in adapter: %s v%s", meta["name"], meta["version"])
        except Exception:
            logger.exception("Failed to load SlackAdapter")

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

                # Wrap with validation if enabled
                if self._validate_outputs:
                    adapter = ValidatedAdapter(adapter)  # type: ignore[assignment]

                # Register adapter
                self._adapters[meta["source"]] = adapter
                logger.info("Loaded plugin adapter: %s v%s (from %s)", meta["name"], meta["version"], ep.name)

            except Exception:
                logger.exception("Failed to load plugin adapter: %s", ep.name)

    def get(self, source_identifier: str) -> InputAdapter:
        """Get adapter by source identifier.

        Args:
            source_identifier: Source identifier (e.g., "whatsapp", "slack")

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
    global _global_registry
    if _global_registry is None:
        _global_registry = InputAdapterRegistry()
    return _global_registry
