"""Abstract base class for input sources (WhatsApp, Slack, Discord, etc.)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ibis.expr.types import Table


@dataclass
class InputMetadata:
    """Metadata about the input source."""

    source_type: str  # "whatsapp", "slack", "discord", etc.
    group_name: str  # Display name of the group/channel
    group_slug: str  # URL-safe identifier
    export_date: date  # Date when the export was created
    timezone: str | None = None  # Timezone of the source data
    additional_metadata: dict[str, Any] | None = None  # Source-specific metadata


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
    def parse(self, source_path: Path, **kwargs) -> tuple[Table, InputMetadata]:
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
    def extract_media(self, source_path: Path, output_dir: Path, **kwargs) -> dict[str, str]:
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


class InputSourceRegistry:
    """Registry for managing available input sources."""

    def __init__(self) -> None:
        self._sources: dict[str, type[InputSource]] = {}

    def register(self, source_class: type[InputSource]) -> None:
        """Register an input source class.

        Args:
            source_class: Class inheriting from InputSource

        """
        instance = source_class()
        self._sources[instance.source_type] = source_class

    def get_source(self, source_type: str) -> InputSource:
        """Get an input source by type.

        Args:
            source_type: Type identifier (e.g., 'whatsapp')

        Returns:
            Instance of the requested input source

        Raises:
            KeyError: If source_type is not registered

        """
        if source_type not in self._sources:
            available = ", ".join(self._sources.keys())
            msg = f"Input source '{source_type}' not found. Available: {available}"
            raise KeyError(msg)
        return self._sources[source_type]()

    def detect_source(self, source_path: Path) -> InputSource | None:
        """Auto-detect the appropriate input source for a given path.

        Args:
            source_path: Path to analyze

        Returns:
            Instance of detected input source, or None if no match

        """
        for source_class in self._sources.values():
            instance = source_class()
            if instance.supports_format(source_path):
                return instance
        return None

    def list_sources(self) -> list[str]:
        """List all registered input source types."""
        return list(self._sources.keys())


# Global registry instance
input_registry = InputSourceRegistry()
