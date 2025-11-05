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
    1. Parsing raw exports from a specific platform (REQUIRED)
    2. Converting messages to the standardized IR schema (REQUIRED)
    3. Optionally extracting media files and providing a mapping (OPTIONAL)
    4. Optionally providing export metadata (OPTIONAL)

    Required Methods:
        - source_name (property): Human-readable name
        - source_identifier (property): CLI identifier
        - parse(): Convert raw export to IR-compliant table

    Optional Methods (with default implementations):
        - extract_media(): Extract bundled media files
        - get_metadata(): Extract export metadata

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

        **Media References**: Messages should include media as markdown links:
        - Images: `![alt text](filename.jpg)`
        - Videos/Files: `[link text](filename.mp4)`

        The adapter should use original filenames/references. The runner will:
        1. Extract markdown references
        2. Call `deliver_media()` to get the actual files
        3. Standardize naming (content-hash based UUIDs)
        4. Replace references with standardized paths

        Args:
            input_path: Path to the raw export (ZIP file, JSON, etc.)
            timezone: Timezone for timestamp normalization (if applicable)
            **kwargs: Source-specific parameters

        Returns:
            Ibis Table conforming to IR_SCHEMA with columns:
                - timestamp: Timestamp with timezone
                - date: Date derived from timestamp
                - author: Anonymized author identifier
                - message: Message content (with markdown media links)
                - original_line: Raw source line (debugging)
                - tagged_line: Processing tracking
                - message_id: Deterministic message ID

        Raises:
            ValueError: If input is invalid or cannot be parsed
            FileNotFoundError: If input_path does not exist

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> table = adapter.parse(Path("export.zip"), timezone="UTC")
            >>> # Table contains: "Check this out ![photo](IMG-001.jpg)"
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
        """Extract media files from the export (OPTIONAL).

        Some sources bundle media with the export (e.g., WhatsApp ZIP).
        This method extracts media files to the output directory and returns
        a mapping that the core pipeline can use to rewrite message references.

        **This method is optional.** The default implementation returns an empty
        dictionary, indicating no media extraction. Override this method only if
        your source includes bundled media files.

        Args:
            input_path: Path to the raw export
            output_dir: Directory where media should be extracted
            **kwargs: Source-specific parameters

        Returns:
            Dictionary mapping message references to extracted file paths.
            Default: empty dict (no media)
            Example: {"image.jpg": Path("media/2024-01-15-image.jpg")}

        Note:
            For sources where media is handled elsewhere (e.g., via URLs or
            period-specific extraction), returning an empty dict is appropriate.
            The pipeline will handle media extraction at the appropriate stage.
        """
        return {}

    def deliver_media(
        self,
        media_reference: str,
        temp_dir: Path,
        **kwargs: Any,
    ) -> Path | None:
        """Deliver media file to temporary directory (OPTIONAL).

        This method is called lazily by the runner for each media reference
        found in markdown links. The adapter is responsible for obtaining the
        actual file content and writing it to the temp directory.

        **Implementation Examples:**
        - WhatsApp: Extract file from ZIP archive
        - Slack: Download file from URL
        - Discord: Download from CDN with authentication
        - Local files: Copy from filesystem

        **Content-based naming**: The runner will hash the file content and
        rename it using UUIDv5 for deduplication. The adapter just needs to
        deliver the original file.

        Args:
            media_reference: Media reference from markdown link (e.g., "photo.jpg")
            temp_dir: Temporary directory where file should be written
            **kwargs: Source-specific parameters (e.g., auth tokens, ZIP handle)

        Returns:
            Path to the delivered file in temp_dir, or None if not found

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> # Message contains: ![photo](IMG-001.jpg)
            >>> temp_file = adapter.deliver_media("IMG-001.jpg", Path("/tmp"))
            >>> # Returns: Path("/tmp/IMG-001.jpg")

        Note:
            Default implementation returns None (no media support).
            Override this method if your source can deliver media files.
        """
        return None

    def get_metadata(self, input_path: Path, **kwargs: Any) -> dict[str, Any]:
        """Extract metadata from the export (OPTIONAL).

        **This method is optional.** The default implementation returns an empty
        dictionary. Override this method to provide source-specific metadata.

        Metadata may include:
        - Group/channel name
        - Export date
        - Number of participants
        - Date range of messages
        - Any other source-specific information

        Args:
            input_path: Path to the raw export
            **kwargs: Source-specific parameters

        Returns:
            Dictionary with source-specific metadata
            Default: empty dict

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> metadata = adapter.get_metadata(Path("export.zip"))
            >>> print(metadata["group_name"])
            'My Group Chat'
        """
        return {}

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(source='{self.source_identifier}')"
