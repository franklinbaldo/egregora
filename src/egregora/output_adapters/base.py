"""Abstract base class for output formats (MkDocs, Hugo, Jekyll, etc.)."""

import datetime
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Protocol, runtime_checkable

import ibis
import ibis.expr.datatypes as dt

from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlConvention

if TYPE_CHECKING:
    from ibis.expr.types import Table

# Constants
ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)
FILENAME_PARTS_WITH_EXTENSION = 2  # Parts when splitting filename by "." (name, extension)

DOCUMENT_INVENTORY_SCHEMA = ibis.schema(
    {
        "storage_identifier": dt.string,
        "mtime_ns": dt.Int64(nullable=True),
    }
)


@dataclass
class SiteConfiguration:
    """Configuration for a documentation/blog site."""

    site_root: Path
    site_name: str
    docs_dir: Path
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path
    config_file: Path | None
    additional_paths: dict[str, Path] | None = None


@runtime_checkable
class OutputSink(Protocol):
    """
    Pure data interface.
    Compatible with Filesystems, SQL Databases, Notion API, S3, etc.
    """

    @property
    def url_convention(self) -> UrlConvention:
        """The URL convention used by this sink."""
        ...

    def persist(self, document: Document) -> None:
        """Save a document (create or update)."""
        ...

    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a document."""
        ...

    def list(self, doc_type: DocumentType | None = None) -> Iterator[Document]:
        """List available content (for RAG/History)."""
        ...

    def documents(self) -> Iterator[Document]:
        """Return all managed documents as Document objects.

        This is an alias for list() to maintain backward compatibility during refactoring.
        """
        ...


@runtime_checkable
class SiteScaffolder(Protocol):
    """
    Lifecycle interface.
    Only implemented by adapters that need local filesystem setup.
    """

    def scaffold(self, path: Path, config: dict) -> None:
        """Initialize directory structure, config files, assets."""
        ...

    def validate_structure(self, path: Path) -> bool:
        """Check if the target directory is valid for this adapter."""
        ...


class OutputAdapter(OutputSink, ABC):
    """Abstract base class for output formats.

    Refactored to align with OutputSink protocol.
    Legacy methods removed to enforce Interface Segregation Principle.
    """

    @property
    def docs_dir_name(self) -> str:
        """Default name for the documentation directory."""
        return "docs"

    @property
    def blog_dir_name(self) -> str:
        """Default name for the blog directory (relative to docs_dir)."""
        return "."

    @property
    def profiles_dir_name(self) -> str:
        """Name for the author profiles directory."""
        return "profiles"

    @property
    def media_dir_name(self) -> str:
        """Name for the media/assets directory."""
        return "media"

    def get_media_url_path(self, media_file: Path, site_root: Path) -> str:
        """Get the relative URL path for a media file in the generated site.

        Args:
            media_file: Absolute path to the media file
            site_root: Root directory of the site

        Returns:
            Relative path string for use in HTML/markdown links
            Example: "media/images/abc123.jpg"

        """
        # This relies on resolve_paths which is no longer in the base interface.
        # Subclasses (like MkDocsAdapter) should override if they need this logic,
        # or it should be moved to the specific adapter.
        # For now, we leave it but it might fail if resolve_paths is called on self
        # and self doesn't implement it (OutputAdapter doesn't enforce it anymore).
        # Assuming subclasses will implement what they need.
        # Ideally, this method should be abstract or removed if it depends on removed methods.
        raise NotImplementedError("Subclasses must implement get_media_url_path")

    def get_profile_url_path(self, profile_slug: str) -> str:
        """Get the relative URL path for a profile page."""
        return f"{self.profiles_dir_name}/{profile_slug}/"

    def get_post_url_path(self, post_slug: str) -> str:
        """Get the relative URL path for a blog post."""
        return f"posts/{post_slug}/"

    @abstractmethod
    def load_config(self, site_root: Path) -> dict[str, Any]:
        """Load site configuration."""

    @abstractmethod
    def supports_site(self, site_root: Path) -> bool:
        """Check if this output format can handle the given site."""

    @property
    @abstractmethod
    def format_type(self) -> str:
        """Return the type identifier for this format (e.g., 'mkdocs', 'hugo')."""

    @abstractmethod
    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for this format."""

    @abstractmethod
    def get_format_instructions(self) -> str:
        """Generate format-specific instructions for the writer agent."""

    def list_documents(self) -> "Table":
        """List all documents managed by this output format as an Ibis table.

        The default implementation materializes the documents returned by
        :meth:`documents` and exposes their storage identifiers and mtimes.
        Override only if you need to source the table from another store.
        """
        rows: list[dict[str, Any]] = []
        for document in self.documents():
            identifier = document.metadata.get("storage_identifier")
            if not identifier:
                identifier = document.suggested_path
            if not identifier:
                continue

            mtime_ns = document.metadata.get("mtime_ns")
            if mtime_ns is None:
                try:
                    path = Path(document.metadata.get("source_path", identifier))
                    if path.exists():
                        mtime_ns = path.stat().st_mtime_ns
                except OSError:
                    mtime_ns = None

            rows.append({"storage_identifier": identifier, "mtime_ns": mtime_ns})
        return ibis.memtable(rows, schema=DOCUMENT_INVENTORY_SCHEMA)

    @abstractmethod
    def resolve_document_path(self, identifier: str) -> Path:
        """Resolve storage identifier to absolute filesystem path.

        Note: This assumes filesystem backing. Non-filesystem adapters
        might raise NotImplementedError or return a temp path.
        """

    @abstractmethod
    def initialize(self, site_root: Path) -> None:
        """Initialize internal state for a specific site."""

    # ===== Common Utility Methods (Concrete) =====

    def _scan_directory_for_documents(
        self,
        directory: Path,
        site_root: Path,
        pattern: str = "*.md",
        *,
        recursive: bool = False,
        exclude_names: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Scan a directory for documents and return metadata."""
        if not directory.exists():
            return []

        exclude_names = exclude_names or set()
        documents = []

        glob_func = directory.rglob if recursive else directory.glob
        for file_path in glob_func(pattern):
            if not file_path.is_file():
                continue
            if file_path.name in exclude_names:
                continue

            try:
                relative_path = str(file_path.relative_to(site_root))
                mtime_ns = file_path.stat().st_mtime_ns
                documents.append({"storage_identifier": relative_path, "mtime_ns": mtime_ns})
            except (OSError, ValueError):
                continue

        return documents

    def _empty_document_table(self) -> "Table":
        """Return an empty Ibis table with the document listing schema."""
        return ibis.memtable([], schema=ibis.schema({"storage_identifier": "string", "mtime_ns": "int64"}))

    def _documents_to_table(self, documents: list[dict[str, Any]]) -> "Table":
        """Convert list of document dicts to Ibis table."""
        schema = ibis.schema({"storage_identifier": "string", "mtime_ns": "int64"})
        return ibis.memtable(documents, schema=schema)

    @staticmethod
    def normalize_slug(slug: str) -> str:
        """Normalize slug to be URL-safe and filesystem-safe."""
        from egregora.utils import slugify

        return slugify(slug)

    @staticmethod
    def extract_date_prefix(date_str: str) -> str:
        """Extract clean YYYY-MM-DD date from various formats."""
        if not date_str:
            return datetime.date.today().isoformat()

        date_str = date_str.strip()

        # Try ISO date first (YYYY-MM-DD)
        if len(date_str) == ISO_DATE_LENGTH and date_str[4] == "-" and date_str[7] == "-":
            try:
                datetime.date.fromisoformat(date_str)
            except (ValueError, AttributeError):
                pass
            else:
                return date_str

        # Extract YYYY-MM-DD pattern from longer strings
        match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
        if match:
            clean_date = match.group(1)
            try:
                datetime.date.fromisoformat(clean_date)
            except (ValueError, AttributeError):
                pass
            else:
                return clean_date

        # Fallback: use today's date
        return datetime.date.today().isoformat()

    @staticmethod
    def generate_unique_filename(base_dir: Path, filename_pattern: str, max_attempts: int = 1000) -> Path:
        """Generate unique filename by adding suffix if file exists."""
        from egregora.utils import safe_path_join

        # Try original filename first
        if "{suffix}" not in filename_pattern:
            # Add suffix placeholder before extension
            parts = filename_pattern.rsplit(".", 1)
            if len(parts) == FILENAME_PARTS_WITH_EXTENSION:
                filename_pattern = f"{parts[0]}{{suffix}}.{parts[1]}"
            else:
                filename_pattern = f"{filename_pattern}{{suffix}}"

        # Try without suffix first
        original_filename = filename_pattern.replace("{suffix}", "")
        filepath = safe_path_join(base_dir, original_filename)

        if not filepath.exists():
            return filepath

        # Generate with suffix
        for suffix in range(2, max_attempts + 2):
            filename = filename_pattern.replace("{suffix}", f"-{suffix}")
            filepath = safe_path_join(base_dir, filename)

            if not filepath.exists():
                return filepath

        msg = f"Could not generate unique filename after {max_attempts} attempts: {filename_pattern}"
        raise RuntimeError(msg)

    def parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """Parse frontmatter from markdown content."""
        import yaml

        if not content.startswith("---\n"):
            return {}, content

        # Find end of frontmatter
        end_marker = content.find("\n---\n", 4)
        if end_marker == -1:
            return {}, content

        # Extract and parse frontmatter
        frontmatter_text = content[4:end_marker]
        body = content[end_marker + 5 :].lstrip()

        try:
            metadata = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            msg = f"Invalid YAML frontmatter: {e}"
            raise ValueError(msg) from e

        return metadata, body

    def prepare_window(
        self, window_label: str, _window_data: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Pre-processing hook called before writer agent processes a window."""
        # Base implementation does nothing - subclasses override for specific tasks
        return None

    def finalize_window(  # noqa: B027
        self,
        window_label: str,
        posts_created: list[str],
        profiles_updated: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Post-processing hook called after writer agent completes a window."""
        # Base implementation does nothing - subclasses override for specific tasks


class OutputAdapterRegistry:
    """Registry for managing available output formats."""

    def __init__(self) -> None:
        self._formats: dict[str, type[OutputAdapter]] = {}

    def register(self, format_class: type[OutputAdapter]) -> None:
        """Register an output format class."""
        instance = format_class()
        self._formats[instance.format_type] = format_class

    def get_format(self, format_type: str) -> OutputAdapter:
        """Get an output format by type."""
        if format_type not in self._formats:
            available = ", ".join(self._formats.keys())
            msg = f"Output format '{format_type}' not found. Available: {available}"
            raise KeyError(msg)
        return self._formats[format_type]()

    def detect_format(self, site_root: Path) -> OutputAdapter | None:
        """Auto-detect the appropriate output format for a given site."""
        for format_class in self._formats.values():
            instance = format_class()
            if instance.supports_site(site_root):
                return instance
        return None

    def list_formats(self) -> list[str]:
        """List all registered output format types."""
        return list(self._formats.keys())


output_registry = OutputAdapterRegistry()


def create_output_format(site_root: Path, format_type: str = "mkdocs") -> OutputAdapter:
    """Create and initialize an OutputAdapter based on configuration."""
    # Ensure registry is populated by importing rendering module
    # This triggers registration in rendering/__init__.py

    # Get format class from registry
    output_format = output_registry.get_format(format_type)

    # Initialize with site_root
    output_format.initialize(site_root)

    return output_format
