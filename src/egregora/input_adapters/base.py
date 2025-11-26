"""Base classes and interfaces for platform-specific sources.

This module provides the core abstractions for implementing chat platform adapters:

1. **InputAdapter** (Modern Interface):
   - The standard adapter interface for all sources
   - Returns Table directly conforming to IR schema
   - Supports media delivery and content-hash UUIDs
   - All new implementations must use this interface

2. **Export** (Data Class):
   - Common metadata for chat exports
   - Platform-specific implementations can extend this

3. **AdapterMeta** (Type):
   - Metadata for adapter discovery and plugin loading
   - Used by adapter registry for validation

Note: This is the only adapter interface. The legacy InputSource has been removed.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID

from egregora.data_primitives.document import Document

if TYPE_CHECKING:
    from ibis.expr.types import Table


logger = logging.getLogger(__name__)

# =============================================================================
# Common Types
# =============================================================================

__all__ = [
    "AdapterMeta",
    "Export",
    "InputAdapter",
    "MediaMapping",
]


class AdapterMeta(TypedDict):
    """Metadata for adapter discovery and plugin loading.

    This metadata is used by the adapter registry to:
    - Display available adapters in CLI (egregora adapters list)
    - Validate IR version compatibility
    - Provide documentation links

    Used by both InputSource and InputAdapter interfaces.

    Attributes:
        name: Adapter identifier (e.g., 'whatsapp', 'slack')
        version: Semantic version (e.g., '1.0.0')
        source: Source platform name (e.g., 'WhatsApp', 'Slack')
        doc_url: Documentation URL
        ir_version: IR version supported (e.g., 'v1')

    Example:
        >>> meta: AdapterMeta = {
        ...     "name": "WhatsApp",
        ...     "version": "1.0.0",
        ...     "source": "whatsapp",
        ...     "doc_url": "https://github.com/franklinbaldo/egregora#whatsapp",
        ...     "ir_version": "v1"
        ... }

    """

    name: str
    version: str
    source: str
    doc_url: str
    ir_version: str


MediaMapping = dict[str, Document]
MEDIA_UUID_NAMESPACE = UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(slots=True)
class Export:
    """Base class for chat export metadata.

    Platform-specific implementations (WhatsApp, Slack, Discord, etc.)
    should inherit from this class and add their specific fields.
    """

    zip_path: Path
    group_name: str
    group_slug: str
    export_date: date
    chat_file: str
    media_files: list[str]


# =============================================================================
# InputAdapter Interface
# =============================================================================


class InputAdapter(ABC):
    """Abstract base class for all source adapters.

    A source adapter is responsible for:
    1. Parsing raw exports from a specific platform (REQUIRED)
    2. Converting messages to the standardized IR schema (REQUIRED)
    3. Optionally extracting media files and providing a mapping (OPTIONAL)
    4. Optionally providing export metadata (OPTIONAL)

    Required Methods:
        - source_name (property): Human-readable name
        - source_identifier (property): CLI identifier
        - get_adapter_metadata(): Return adapter metadata for plugin discovery
        - parse(): Convert raw export to IR-compliant table

    Optional Methods (with default implementations):
        - extract_media(): Extract bundled media files
        - deliver_media(): Deliver media file on demand
        - get_metadata(): Extract export metadata

    Adapters should be stateless and reusable.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the human-readable name of this source.

        Examples: "WhatsApp", "Slack", "Discord", "Telegram"
        """

    @property
    @abstractmethod
    def source_identifier(self) -> str:
        """Return the unique identifier for this source.

        Used in CLI and configuration. Should be lowercase, alphanumeric.
        Examples: "whatsapp", "slack", "discord", "telegram"
        """

    @abstractmethod
    def get_adapter_metadata(self) -> AdapterMeta:
        """Return adapter metadata for plugin discovery and validation.

        This method enables:
        - Plugin registry to discover and validate adapters
        - IR version compatibility checking
        - Documentation links for users
        - Version tracking for debugging

        Returns:
            AdapterMeta with name, version, source, doc_url, ir_version

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> meta = adapter.get_adapter_metadata()
            >>> print(f"{meta['name']} v{meta['version']} (IR {meta['ir_version']})")
            WhatsApp v1.0.0 (IR v1)

        """

    @abstractmethod
    def parse(self, input_path: Path, *, timezone: str | None = None, **kwargs: Any) -> Table:
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

        """

    @property
    def content_summary(self) -> str:
        """Describe the type of content this adapter ingests."""
        return f"This adapter processes data exported from {self.source_name}."

    @property
    def generation_instructions(self) -> str:
        """Optional writer guidance injected into prompts."""
        return ""

    def deliver_media(self, _media_reference: str, **_kwargs: Any) -> Document | None:
        """Deliver media file as a Document (OPTIONAL).

        This method is called lazily by the runner for each media reference
        found in markdown links. The adapter is responsible for obtaining the
        actual file content and returning it as a Document object.

        **Implementation Examples:**
        - WhatsApp: Extract file from ZIP archive
        - Slack: Download file from URL
        - Discord: Download from CDN with authentication
        - Local files: Read from filesystem

        The runner will handle content hashing and deduplication based on the
        Document's content bytes.

        Args:
            media_reference: Media reference from markdown link (e.g., "photo.jpg")
            **kwargs: Source-specific parameters (e.g., auth tokens, ZIP handle)

        Returns:
            Document containing the media content, or None if not found.
            The Document type should be MEDIA.

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> # Message contains: ![photo](IMG-001.jpg)
            >>> document = adapter.deliver_media("IMG-001.jpg", zip_path=Path("export.zip"))
            >>> # Returns: Document(content=b'...', type=MEDIA, metadata={'filename': 'IMG-001.jpg'})

        Note:
            Default implementation returns None (no media support).
            Override this method if your source can deliver media files.

        """
        return None

    def get_metadata(self, _input_path: Path, **_kwargs: Any) -> dict[str, Any]:
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
