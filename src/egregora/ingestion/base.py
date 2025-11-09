"""Abstract base class for input sources (WhatsApp, Slack, Discord, etc.)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, TypedDict

from ibis.expr.types import Table

logger = logging.getLogger(__name__)


class AdapterMeta(TypedDict):
    """Metadata for adapter discovery and plugin loading.

    This metadata is used by the adapter registry to:
    - Display available adapters in CLI (egregora adapters list)
    - Validate IR version compatibility
    - Provide documentation links

    Attributes:
        name: Adapter identifier (e.g., 'whatsapp', 'slack')
        version: Semantic version (e.g., '1.0.0')
        source: Source platform name (e.g., 'WhatsApp', 'Slack')
        doc_url: Documentation URL
        ir_version: IR version supported (e.g., 'v1')

    """

    name: str
    version: str
    source: str
    doc_url: str
    ir_version: str


@dataclass
class InputMetadata:
    """Metadata about the input source."""

    source_type: str
    group_name: str
    group_slug: str
    export_date: date
    timezone: str | None = None
    additional_metadata: dict[str, Any] | None = None


class InputSource(ABC):
    """Abstract base class for input sources.

    Input sources are responsible for:
    1. Parsing raw exports/data into standardized Ibis Tables
    2. Extracting media files and references
    3. Providing metadata about the source

    The output Table must conform to MESSAGE_SCHEMA defined in core/schema.py:
    - timestamp: datetime (timezone-aware if possible)
    - date: date (local date)
    - author: string (can be anonymized later)
    - message: string (plain text or markdown)
    - original_line: string (raw input for debugging)
    - tagged_line: string (can be same as message initially)
    - message_id: string (deterministic, unique identifier)
    """

    @abstractmethod
    def parse(self, source_path: Path, **kwargs: Any) -> tuple[Table, InputMetadata]:
        """Parse the input source into a standardized Ibis Table.

        Args:
            source_path: Path to the input file/directory
            **kwargs: Source-specific configuration options

        Returns:
            tuple of (messages_table, metadata)
            - messages_table: Ibis Table conforming to MESSAGE_SCHEMA
            - metadata: InputMetadata with source information

        Raises:
            ValueError: If source_path is invalid or cannot be parsed
            RuntimeError: If parsing fails

        """

    @abstractmethod
    def extract_media(self, source_path: Path, output_dir: Path, **kwargs: Any) -> dict[str, str]:
        """Extract media files from the source.

        Args:
            source_path: Path to the input file/directory
            output_dir: Directory to extract media files to
            **kwargs: Source-specific options

        Returns:
            Mapping of original filename -> extracted file path
            Example: {"IMG-001.jpg": "media/images/img-001.jpg"}

        """

    @abstractmethod
    def supports_format(self, source_path: Path) -> bool:
        """Check if this input source can handle the given file/directory.

        Args:
            source_path: Path to check

        Returns:
            True if this source can parse the given path, False otherwise

        """

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the type identifier for this source (e.g., 'whatsapp', 'slack')."""

    @abstractmethod
    def adapter_meta(self) -> AdapterMeta:
        """Return adapter metadata for plugin discovery.

        Returns:
            AdapterMeta with name, version, source, doc_url, ir_version

        Example:
            >>> def adapter_meta(self) -> AdapterMeta:
            ...     return {
            ...         "name": "whatsapp",
            ...         "version": "1.0.0",
            ...         "source": "WhatsApp",
            ...         "doc_url": "https://docs.egregora.dev/adapters/whatsapp",
            ...         "ir_version": "v1",
            ...     }

        """


class InputSourceRegistry:
    """Registry for managing available input sources.

    Supports both built-in adapters and third-party plugins via entry points.
    Plugins are discovered from the 'egregora.adapters' entry point group.

    Example plugin registration in pyproject.toml:
        [project.entry-points."egregora.adapters"]
        discord = "my_adapter.discord:DiscordInputSource"

    """

    def __init__(self) -> None:
        self._sources: dict[str, type[InputSource]] = {}
        self._plugins_loaded = False

    def register(self, source_class: type[InputSource]) -> None:
        """Register an input source class.

        Args:
            source_class: Class inheriting from InputSource

        """
        instance = source_class()
        self._sources[instance.source_type] = source_class
        logger.debug(f"Registered adapter: {instance.source_type}")

    def _load_plugins(self) -> None:
        """Load third-party adapters from entry points.

        Discovers plugins from the 'egregora.adapters' entry point group.
        Validates IR version compatibility before registering.

        """
        if self._plugins_loaded:
            return  # Already loaded

        try:
            from importlib.metadata import entry_points
        except ImportError:
            # Python < 3.10
            try:
                from importlib_metadata import entry_points  # type: ignore
            except ImportError:
                logger.warning("importlib.metadata not available, plugin loading disabled")
                self._plugins_loaded = True
                return

        # Load plugins from entry points
        eps = entry_points()

        # Handle different entry_points() return types across Python versions
        if hasattr(eps, "select"):
            # Python 3.10+
            adapter_eps = eps.select(group="egregora.adapters")
        else:
            # Python 3.9
            adapter_eps = eps.get("egregora.adapters", [])

        for ep in adapter_eps:
            try:
                # Load adapter class
                adapter_cls = ep.load()
                adapter = adapter_cls()

                # Get metadata
                meta = adapter.adapter_meta()

                # Validate IR version
                if meta["ir_version"] != "v1":
                    logger.warning(
                        f"Adapter '{ep.name}' requires IR {meta['ir_version']}, skipping (only v1 supported)"
                    )
                    continue

                # Register adapter
                self._sources[ep.name] = adapter_cls
                logger.info(f"Loaded plugin adapter: {ep.name} v{meta['version']} (source: {meta['source']})")

            except Exception as e:
                logger.exception(f"Failed to load adapter plugin '{ep.name}': {e}")

        self._plugins_loaded = True

    def get_source(self, source_type: str) -> InputSource:
        """Get an input source by type.

        Loads plugins on first access if not already loaded.

        Args:
            source_type: Type identifier (e.g., 'whatsapp')

        Returns:
            Instance of the requested input source

        Raises:
            KeyError: If source_type is not registered

        """
        self._load_plugins()  # Lazy load plugins

        if source_type not in self._sources:
            available = ", ".join(self._sources.keys()) or "none"
            msg = f"Input source '{source_type}' not found. Available: {available}"
            raise KeyError(msg)
        return self._sources[source_type]()

    def detect_source(self, source_path: Path) -> InputSource | None:
        """Auto-detect the appropriate input source for a given path.

        Loads plugins on first access if not already loaded.

        Args:
            source_path: Path to analyze

        Returns:
            Instance of detected input source, or None if no match

        """
        self._load_plugins()  # Lazy load plugins

        for source_class in self._sources.values():
            instance = source_class()
            if instance.supports_format(source_path):
                return instance
        return None

    def list_sources(self) -> list[str]:
        """List all registered input source types.

        Loads plugins on first access if not already loaded.

        Returns:
            List of source type identifiers

        """
        self._load_plugins()  # Lazy load plugins
        return list(self._sources.keys())

    def get_adapter_metadata(self) -> list[AdapterMeta]:
        """Get metadata for all registered adapters.

        Loads plugins on first access if not already loaded.

        Returns:
            List of AdapterMeta dictionaries

        """
        self._load_plugins()  # Lazy load plugins

        metadata = []
        for source_class in self._sources.values():
            try:
                instance = source_class()
                meta = instance.adapter_meta()
                metadata.append(meta)
            except Exception as e:
                logger.warning(f"Failed to get metadata for {source_class}: {e}")

        return metadata


input_registry = InputSourceRegistry()
