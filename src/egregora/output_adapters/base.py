"""Abstract base class for output formats (MkDocs, Hugo, Jekyll, etc.)."""

import datetime
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import ibis.expr.datatypes as dt

from egregora.data_primitives import DocumentMetadata, OutputSink, UrlConvention
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import DocumentMetadata, OutputSink, UrlConvention

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


class OutputAdapter(OutputSink, ABC):
    """Abstract base class for output formats focused on document IO.

    Output formats are responsible for persisting ``Document`` instances and
    returning them to the pipeline.  Environment management (e.g., scaffolding
    MkDocs projects) is handled separately via :class:`SiteScaffolder`.
    """

    @abstractmethod
    def persist(self, document: Document) -> None:
        """Persist a document so it becomes available at its canonical path."""

    @abstractmethod
    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a single document by its ``doc_type`` primary identifier."""

    @property
    @abstractmethod
    def url_convention(self) -> UrlConvention:
        """Return the URL convention adopted by this adapter."""

    @property
    @abstractmethod
    def format_type(self) -> str:
        """Return the type identifier for this format (e.g., 'mkdocs', 'hugo')."""

    @abstractmethod
    def supports_site(self, site_root: Path) -> bool:
        """Return True if this adapter can manage the given site root."""

    @abstractmethod
    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for this format.

        Returns:
            List of markdown extension identifiers
            Example: ["tables", "fenced_code", "admonitions"]

        """

    @abstractmethod
    def get_format_instructions(self) -> str:
        """Generate format-specific instructions for the writer agent.

        Returns plain text that gets injected into the writer prompt to teach
        the LLM about this output format's conventions (front-matter style,
        file naming, special features, etc.).

        This enables the writer agent to adapt to different formats without
        code changes - the LLM learns format conventions through instructions.

        Returns:
            Markdown-formatted instructions for the writer prompt

        Example output:
            '''
            ## Output Format: MkDocs Material

            Your posts will be rendered using MkDocs with the Material theme.

            **Front-matter format**: YAML (between --- markers)
            **Required fields**: title, date, slug, authors, tags, summary
            **File naming**: {date}-{slug}.md (e.g., 2025-01-10-my-post.md)

            **Special features**:
            - Author attribution via .authors.yml (use UUIDs only)
            - Blog plugin for post listing and RSS
            - Tags create automatic taxonomy pages

            **Markdown extensions enabled**:
            - Admonitions: !!! note, !!! warning, !!! tip
            - Code blocks with syntax highlighting
            - Math: $inline$ and $$block$$
            '''

        """

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """Iterate through available documents, optionally filtering by ``doc_type``."""
        for document in self.documents():
            if doc_type is not None and document.type != doc_type:
                continue

            identifier = document.metadata.get("storage_identifier")
            if not identifier:
                identifier = document.suggested_path
            if not identifier:
                continue

            yield DocumentMetadata(identifier=identifier, doc_type=document.type, metadata=document.metadata)

    def list_documents(self, doc_type: DocumentType | None = None) -> "Table":
        """Compatibility shim returning an Ibis table of document metadata."""
        rows: list[dict[str, Any]] = []
        for meta in self.list(doc_type):
            mtime_ns = meta.metadata.get("mtime_ns") if isinstance(meta.metadata, dict) else None
            if mtime_ns is None:
                try:
                    path = (
                        Path(meta.metadata.get("source_path", meta.identifier))
                        if isinstance(meta.metadata, dict)
                        else None
                    )
                    if path and path.exists():
                        mtime_ns = path.stat().st_mtime_ns
                except OSError:
                    mtime_ns = None

            rows.append({"storage_identifier": meta.identifier, "mtime_ns": mtime_ns})

        return ibis.memtable(rows, schema=DOCUMENT_INVENTORY_SCHEMA)

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Backward-compatible alias for :meth:`get`."""
        return self.get(doc_type, identifier)

    @abstractmethod
    def documents(self) -> Iterator[Document]:
        """Return all managed documents as Document objects (lazy iterator)."""

    @abstractmethod
    def initialize(self, site_root: Path) -> None:
        """Initialize internal state for a specific site.

        Must be called before using helper methods such as ``write_post`` or
        ``serve``.  Implementations should perform any filesystem validation and
        prepare auxiliary helpers needed during a window.

        Args:
            site_root: Root directory of the site

        Raises:
            RuntimeError: If initialization fails
            ValueError: If site_root is invalid

        """

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
        """Scan a directory for documents and return metadata.

        This helper method provides common logic for list_documents() implementations.
        Subclasses can call this for each directory they need to scan.

        Args:
            directory: Directory to scan
            site_root: Site root for computing relative paths
            pattern: Glob pattern for matching files (default: "*.md")
            recursive: Use rglob instead of glob
            exclude_names: Set of filenames to exclude (e.g., {"index.md"})

        Returns:
            List of dicts with schema:
                - storage_identifier: string (relative path from site_root)
                - mtime_ns: int64 (modification time in nanoseconds)

        Example:
            >>> results = self._scan_directory_for_documents(
            ...     self.posts_dir, site_root, "*.md"
            ... )

        """
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
        """Return an empty Ibis table with the document listing schema.

        Returns:
            Empty Ibis table with storage_identifier and mtime_ns columns

        """
        return ibis.memtable([], schema=ibis.schema({"storage_identifier": "string", "mtime_ns": "int64"}))

    def _documents_to_table(self, documents: list[dict[str, Any]]) -> "Table":
        """Convert list of document dicts to Ibis table.

        Args:
            documents: List of dicts with storage_identifier and mtime_ns

        Returns:
            Ibis table with document listing schema

        """
        schema = ibis.schema({"storage_identifier": "string", "mtime_ns": "int64"})
        return ibis.memtable(documents, schema=schema)

    @staticmethod
    def normalize_slug(slug: str) -> str:
        """Normalize slug to be URL-safe and filesystem-safe.

        Converts to lowercase, replaces spaces/special chars with hyphens.
        All output formats should use this for consistent slug handling.

        Args:
            slug: Raw slug from metadata (may contain spaces, capitals, etc.)

        Returns:
            Normalized slug (lowercase, hyphens only)

        Examples:
            >>> OutputAdapter.normalize_slug("My Great Post!")
            'my-great-post'
            >>> OutputAdapter.normalize_slug("AI & Machine Learning")
            'ai-machine-learning'

        """
        from egregora.utils import slugify

        return slugify(slug)

    @staticmethod
    def extract_date_prefix(date_str: str) -> str:
        """Extract clean YYYY-MM-DD date from various formats.

        Handles:
        - Clean dates: "2025-03-02"
        - ISO timestamps: "2025-03-02T10:30:00"
        - Window labels: "2025-03-02 08:01 to 12:49"
        - Datetimes: "2025-03-02 10:30:45"

        All output formats should use this for consistent date handling.

        Args:
            date_str: Date string in various formats

        Returns:
            Clean date in YYYY-MM-DD format, or today's date if parsing fails

        Examples:
            >>> OutputAdapter.extract_date_prefix("2025-03-02")
            '2025-03-02'
            >>> OutputAdapter.extract_date_prefix("2025-03-02 10:00 to 12:00")
            '2025-03-02'

        """
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
        """Generate unique filename by adding suffix if file exists.

        Pattern for preventing silent overwrites - all formats should use this.

        Args:
            base_dir: Directory where file will be created
            filename_pattern: Filename template with optional {suffix} placeholder
                             e.g., "2025-01-10-my-post.md" or "2025-01-10-my-post{suffix}.md"
            max_attempts: Maximum number of suffix attempts (default 1000)

        Returns:
            Unique filepath that doesn't exist

        Raises:
            RuntimeError: If unique filename cannot be generated after max_attempts

        Examples:
            >>> # If file doesn't exist
            >>> generate_unique_filename(Path("/posts"), "my-post.md")
            Path("/posts/my-post.md")

            >>> # If file exists, adds -2, -3, etc.
            >>> generate_unique_filename(Path("/posts"), "my-post.md")
            Path("/posts/my-post-2.md")

        """
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
        """Parse frontmatter from markdown content.

        Default implementation handles YAML frontmatter (used by MkDocs, Jekyll).
        Override in subclasses for format-specific frontmatter (Hugo uses TOML).

        Args:
            content: Raw markdown with frontmatter

        Returns:
            (metadata dict, body string)

        Raises:
            ValueError: If frontmatter is malformed

        """
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
        """Pre-processing hook called before writer agent processes a window.

        Template Method pattern - base implementation does nothing, subclasses
        override to perform format-specific preparation tasks.

        Examples of format-specific preparation:
        - Database: Begin transaction, lock tables
        - S3: Download existing posts for modification
        - MkDocs: Validate .authors.yml before starting

        Args:
            window_label: Window identifier (e.g., "2025-01-10 10:00 to 12:00")
            window_data: Optional metadata about the window (message count, date range, etc.)

        Returns:
            Optional context dict to pass to finalize_window()

        Note:
            This method is called even for empty windows.
            Implementations should be idempotent and handle errors gracefully.

        Examples:
            >>> # Database implementation
            >>> def prepare_window(self, window_label, window_data):
            >>>     self.connection.begin()
            >>>     return {"transaction_id": self.connection.transaction_id}

        """
        # Base implementation does nothing - subclasses override for specific tasks
        return None

    def finalize_window(
        self,
        window_label: str,
        posts_created: list[str],
        profiles_updated: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Post-processing hook called after writer agent completes a window.

        Template Method pattern - base implementation does nothing, subclasses
        override to perform format-specific finalization tasks.

        Examples of format-specific finalization:
        - MkDocs: Update .authors.yml, regenerate navigation, update tags index
        - Hugo: Run Hugo build to regenerate site, update taxonomies
        - Database: Commit transaction, update search indexes, vacuum
        - S3: Upload changed files to S3, invalidate CloudFront cache

        Args:
            window_label: Window identifier (e.g., "2025-01-10 10:00 to 12:00")
            posts_created: List of post identifiers created during this window
            profiles_updated: List of profile identifiers updated during this window
            metadata: Optional metadata about the window (duration, token count, context from prepare_window)

        Note:
            This method is called even if no posts/profiles were created.
            Implementations should be idempotent and handle empty lists gracefully.

        Examples:
            >>> # MkDocs implementation
            >>> def finalize_window(self, window_label, posts_created, profiles_updated, metadata):
            >>>     self._update_authors_yml(profiles_updated)
            >>>     self._regenerate_tags_index(posts_created)
            >>>     logger.info(f"Finalized MkDocs window: {window_label}")

            >>> # Database implementation
            >>> def finalize_window(self, window_label, posts_created, profiles_updated, metadata):
            >>>     self.connection.commit()
            >>>     self._update_search_index(posts_created)
            >>>     logger.info(f"Committed database window: {window_label}")

        """
        # Base implementation does nothing - subclasses override for specific tasks


class OutputAdapterRegistry:
    """Registry for managing available output formats."""

    def __init__(self) -> None:
        self._formats: dict[str, type[OutputAdapter]] = {}

    def register(self, format_class: type[OutputAdapter]) -> None:
        """Register an output format class.

        Args:
            format_class: Class inheriting from OutputAdapter

        """
        instance = format_class()
        self._formats[instance.format_type] = format_class

    def get_format(self, format_type: str) -> OutputAdapter:
        """Get an output format by type.

        Args:
            format_type: Type identifier (e.g., 'mkdocs')

        Returns:
            Instance of the requested output format

        Raises:
            KeyError: If format_type is not registered

        """
        if format_type not in self._formats:
            available = ", ".join(self._formats.keys())
            msg = f"Output format '{format_type}' not found. Available: {available}"
            raise KeyError(msg)
        return self._formats[format_type]()

    def detect_format(self, site_root: Path) -> OutputAdapter | None:
        """Auto-detect the appropriate output format for a given site.

        Args:
            site_root: Path to analyze

        Returns:
            Instance of detected output format, or None if no match

        """
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
    """Create and initialize an OutputAdapter based on configuration.

    This is the main factory function for creating output formats. It uses the
    output_registry to get the appropriate format class and initializes it.

    Industry standard: Configuration-driven factory pattern.
    Format type specified in .egregora/config.yml, defaults to mkdocs.

    Args:
        site_root: Root directory for the site
        format_type: Output format type from config (e.g., 'mkdocs')

    Returns:
        Initialized OutputAdapter instance

    Raises:
        KeyError: If format_type is not registered
        RuntimeError: If format initialization fails

    Examples:
        >>> # From config: output.format = "mkdocs"
        >>> fmt = create_output_format(site_root, format_type="mkdocs")

    Note:
        This function automatically ensures the registry is populated by
        importing egregora.rendering (which registers the supported formats).

    """
    # Ensure registry is populated by importing rendering module
    # This triggers registration in rendering/__init__.py

    # Get format class from registry
    output_format = output_registry.get_format(format_type)

    # Initialize with site_root
    output_format.initialize(site_root)

    return output_format
