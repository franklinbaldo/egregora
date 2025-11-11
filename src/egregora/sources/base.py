"""Base classes and interfaces for platform-specific sources.

This module provides the core abstractions for implementing chat platform adapters:

1. **InputSource** (Legacy Interface):
   - Original adapter interface from ingestion/base.py
   - Returns tuple of (Table, InputMetadata)
   - Used by older implementations

2. **SourceAdapter** (Modern Interface):
   - New adapter interface from pipeline/adapters.py
   - Returns Table directly
   - Supports media delivery and content-hash UUIDs
   - Preferred for new implementations

3. **Export** (Data Class):
   - Common metadata for chat exports
   - Platform-specific implementations can extend this

4. **Registries**:
   - InputSourceRegistry: Plugin discovery for InputSource adapters
   - See adapters/registry.py for SourceAdapter registry

Note: Both interfaces coexist during migration. New code should use SourceAdapter.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID, uuid5

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.types import GroupSlug

logger = logging.getLogger(__name__)

# =============================================================================
# Common Types
# =============================================================================

__all__ = [
    "AdapterMeta",
    "Export",
    "InputMetadata",
    "InputSource",
    "InputSourceRegistry",
    "MediaMapping",
    "SourceAdapter",
    "input_registry",
]


class AdapterMeta(TypedDict):
    """Metadata for adapter discovery and plugin loading.

    This metadata is used by the adapter registry to:
    - Display available adapters in CLI (egregora adapters list)
    - Validate IR version compatibility
    - Provide documentation links

    Used by both InputSource and SourceAdapter interfaces.

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


MediaMapping = dict[str, Path]
MEDIA_UUID_NAMESPACE = UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class InputMetadata:
    """Metadata about the input source.

    Used by InputSource.parse() to return export metadata.
    """

    source_type: str
    group_name: str
    group_slug: str
    export_date: date
    timezone: str | None = None
    additional_metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class Export:
    """Base class for chat export metadata.

    Platform-specific implementations (WhatsApp, Slack, Discord, etc.)
    should inherit from this class and add their specific fields.
    """

    zip_path: Path
    group_name: str
    group_slug: GroupSlug
    export_date: date
    chat_file: str
    media_files: list[str]


# =============================================================================
# Legacy InputSource Interface (ingestion/base.py)
# =============================================================================


class InputSource(ABC):
    """Abstract base class for input sources (LEGACY INTERFACE).

    Input sources are responsible for:
    1. Parsing raw exports/data into standardized Ibis Tables
    2. Extracting media files and references
    3. Providing metadata about the source

    The output Table must conform to MESSAGE_SCHEMA defined in database/schema.py:
    - timestamp: datetime (timezone-aware if possible)
    - date: date (local date)
    - author: string (can be anonymized later)
    - message: string (plain text or markdown)
    - original_line: string (raw input for debugging)
    - tagged_line: string (can be same as message initially)
    - message_id: string (deterministic, unique identifier)

    Note: This is the legacy interface. New implementations should use SourceAdapter.
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
    """Registry for managing available input sources (LEGACY).

    Supports both built-in adapters and third-party plugins via entry points.
    Plugins are discovered from the 'egregora.adapters' entry point group.

    Note: This is the legacy registry for InputSource. For SourceAdapter,
    see adapters/registry.py (AdapterRegistry).

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
        logger.debug("Registered adapter: %s", instance.source_type)

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
                from importlib_metadata import entry_points  # type: ignore[import-not-found]
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
                        "Adapter '%s' requires IR %s, skipping (only v1 supported)",
                        ep.name,
                        meta["ir_version"],
                    )
                    continue

                # Register adapter
                self._sources[ep.name] = adapter_cls
                logger.info(
                    "Loaded plugin adapter: %s v%s (source: %s)", ep.name, meta["version"], meta["source"]
                )

            except Exception:
                logger.exception("Failed to load adapter plugin '%s'", ep.name)

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
            except (TypeError, ValueError, AttributeError):
                logger.warning("Failed to get metadata for %s", source_class)

        return metadata


# Global registry instance
input_registry = InputSourceRegistry()


# =============================================================================
# Modern SourceAdapter Interface (pipeline/adapters.py)
# =============================================================================


class SourceAdapter(ABC):
    """Abstract base class for all source adapters (MODERN INTERFACE).

    A source adapter is responsible for:
    1. Parsing raw exports from a specific platform (REQUIRED)
    2. Converting messages to the standardized IR schema (REQUIRED)
    3. Optionally extracting media files and providing a mapping (OPTIONAL)
    4. Optionally providing export metadata (OPTIONAL)

    Required Methods:
        - source_name (property): Human-readable name
        - source_identifier (property): CLI identifier
        - adapter_meta(): Return adapter metadata for plugin discovery
        - parse(): Convert raw export to IR-compliant table

    Optional Methods (with default implementations):
        - extract_media(): Extract bundled media files
        - deliver_media(): Deliver media file on demand
        - get_metadata(): Extract export metadata

    Adapters should be stateless and reusable.

    Note: This is the modern interface introduced in the pipeline refactoring.
    Prefer this over InputSource for new implementations.
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
    def adapter_meta(self) -> AdapterMeta:
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
            >>> meta = adapter.adapter_meta()
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

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> table = adapter.parse(Path("export.zip"), timezone="UTC")
            >>> # Table contains: "Check this out ![photo](IMG-001.jpg)"
            >>> is_valid, errors = validate_ir_schema(table)
            >>> assert is_valid, f"Schema validation failed: {errors}"

        """

    def extract_media(self, _input_path: Path, _output_dir: Path, **_kwargs: Any) -> MediaMapping:
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

    def deliver_media(self, _media_reference: str, _temp_dir: Path, **_kwargs: Any) -> Path | None:
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

    @staticmethod
    def generate_media_uuid(file_path: Path) -> str:
        """Generate content-hash based UUID for media file (HELPER METHOD).

        This is a concrete helper method provided by the base class for
        standardizing media filenames. Adapters and runners can use this
        to ensure consistent UUID generation across all sources.

        Creates a deterministic UUIDv5 from the file's SHA-256 hash, enabling:
        - Deduplication: Same content = same UUID
        - Source-agnostic: Works for any file from any source
        - Clean naming: No date prefixes, just {uuid}.{ext}

        Args:
            file_path: Path to the media file

        Returns:
            UUID string (e.g., "a1b2c3d4-e5f6-5789-a1b2-c3d4e5f67890")

        Example:
            >>> uuid1 = SourceAdapter.generate_media_uuid(Path("photo1.jpg"))
            >>> uuid2 = SourceAdapter.generate_media_uuid(Path("photo1_copy.jpg"))
            >>> uuid1 == uuid2  # True if content is identical

        """
        sha256 = hashlib.sha256()
        with file_path.open("rb") as f:
            # Read in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        content_hash = sha256.hexdigest()
        media_uuid = uuid5(MEDIA_UUID_NAMESPACE, content_hash)
        return str(media_uuid)

    def standardize_media_file(
        self, source_file: Path, media_dir: Path, *, get_subfolder: callable | None = None
    ) -> Path:
        """Standardize a media file with content-hash UUID (HELPER METHOD).

        This is a concrete helper method provided by the base class for
        standardizing media files. It:
        1. Generates content-hash based UUID
        2. Determines subfolder (images/, videos/, etc.)
        3. Moves file to standardized location
        4. Handles deduplication (same content = don't copy)

        Args:
            source_file: Path to the source media file
            media_dir: Base media directory (e.g., docs/media)
            get_subfolder: Optional function to determine subfolder from extension
                          If None, files go directly in media_dir

        Returns:
            Absolute path to standardized file

        Example:
            >>> from egregora.enrichment.media import get_media_subfolder
            >>> adapter = WhatsAppAdapter()
            >>> standardized = adapter.standardize_media_file(
            ...     Path("/tmp/IMG-001.jpg"),
            ...     Path("docs/media"),
            ...     get_subfolder=get_media_subfolder
            ... )
            >>> print(standardized)
            /abs/path/docs/media/images/abc123-uuid.jpg

        """
        media_uuid = self.generate_media_uuid(source_file)
        file_extension = source_file.suffix
        if get_subfolder:
            subfolder = get_subfolder(file_extension)
            target_dir = media_dir / subfolder
        else:
            target_dir = media_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        standardized_name = f"{media_uuid}{file_extension}"
        standardized_path = target_dir / standardized_name
        try:
            source_file.rename(standardized_path)
            logger.debug("Standardized media: %s → %s", source_file.name, standardized_name)
        except FileExistsError:
            logger.debug("Media file already exists (duplicate): %s", standardized_name)
            source_file.unlink()
        except OSError as e:
            if e.errno == 18:
                logger.debug("Cross-filesystem move detected, using shutil.move()")
                try:
                    shutil.move(str(source_file), str(standardized_path))
                    logger.debug("Standardized media: %s → %s", source_file.name, standardized_name)
                except FileExistsError:
                    logger.debug("Media file already exists (duplicate): %s", standardized_name)
                    if source_file.exists():
                        source_file.unlink()
            else:
                raise
        return standardized_path.resolve()

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(source='{self.source_identifier}')"
