"""Source Adapter interface for source-agnostic pipeline.

This module defines the abstract interface that all source adapters must implement.
Source adapters are responsible for parsing raw exports from different platforms
(WhatsApp, Slack, Discord, etc.) into the standardized Intermediate Representation (IR).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ibis.expr.types import Table

__all__ = [
    "MediaMapping",
    "SourceAdapter",
]


# Type alias for media mapping: {reference_in_message: actual_file_path}
MediaMapping = dict[str, Path]


class SourceAdapter(ABC):
    """Abstract base class for all source adapters.

    A source adapter is responsible for:
    1. Parsing raw exports from a specific platform
    2. Converting messages to the standardized IR schema
    3. Optionally extracting media files and providing a mapping

    Adapters should be stateless and reusable.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the human-readable name of this source.

        Examples: "WhatsApp", "Slack", "Discord", "Telegram"
        """
        pass

    @property
    @abstractmethod
    def source_identifier(self) -> str:
        """Return the unique identifier for this source.

        Used in CLI and configuration. Should be lowercase, alphanumeric.
        Examples: "whatsapp", "slack", "discord", "telegram"
        """
        pass

    @abstractmethod
    def parse(
        self,
        input_path: Path,
        *,
        timezone: str | None = None,
        **kwargs: Any,
    ) -> Table:
        """Parse the raw export and return an IR-compliant Ibis Table.

        This is the primary method that converts source-specific data into
        the standardized Intermediate Representation.

        Args:
            input_path: Path to the raw export (ZIP file, JSON, etc.)
            timezone: Timezone for timestamp normalization (if applicable)
            **kwargs: Source-specific parameters

        Returns:
            Ibis Table conforming to IR_SCHEMA with columns:
                - timestamp: Timestamp with timezone
                - date: Date derived from timestamp
                - author: Anonymized author identifier
                - message: Message content
                - original_line: Raw source line (debugging)
                - tagged_line: Processing tracking
                - message_id: Deterministic message ID

        Raises:
            ValueError: If input is invalid or cannot be parsed
            FileNotFoundError: If input_path does not exist

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> table = adapter.parse(Path("export.zip"), timezone="UTC")
            >>> is_valid, errors = validate_ir_schema(table)
            >>> assert is_valid, f"Schema validation failed: {errors}"
        """
        pass

    def extract_media(
        self,
        input_path: Path,
        output_dir: Path,
        **kwargs: Any,
    ) -> MediaMapping:
        """Extract media files from the export (optional).

        Some sources bundle media with the export (e.g., WhatsApp ZIP).
        This method extracts media files to the output directory and returns
        a mapping that the core pipeline can use to rewrite message references.

        Args:
            input_path: Path to the raw export
            output_dir: Directory where media should be extracted
            **kwargs: Source-specific parameters

        Returns:
            Dictionary mapping message references to extracted file paths.
            Example: {"image.jpg": Path("media/2024-01-15-image.jpg")}

        Raises:
            NotImplementedError: If source doesn't support media extraction

        Note:
            Default implementation returns empty dict (no media).
            Override this method if your source includes media files.
        """
        return {}

    def get_metadata(self, input_path: Path, **kwargs: Any) -> dict[str, Any]:
        """Extract metadata from the export (optional).

        Metadata may include:
        - Group/channel name
        - Export date
        - Number of participants
        - Date range of messages

        Args:
            input_path: Path to the raw export
            **kwargs: Source-specific parameters

        Returns:
            Dictionary with source-specific metadata

        Note:
            Default implementation returns empty dict.
            Override this method to provide source-specific metadata.
        """
        return {}

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(source='{self.source_identifier}')"
