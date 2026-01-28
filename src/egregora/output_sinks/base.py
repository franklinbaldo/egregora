"""Abstract base class for output formats (MkDocs, Hugo, Jekyll, etc.)."""

from __future__ import annotations

import builtins
import datetime
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from egregora.data_primitives import DocumentMetadata, OutputSink, UrlConvention
from egregora.data_primitives.text import slugify
from egregora.output_sinks.exceptions import (
    AdapterNotDetectedError,
    FilenameGenerationError,
    FrontmatterParsingError,
    RegistryNotProvidedError,
)
from egregora.security.fs import safe_path_join

if TYPE_CHECKING:
    from collections.abc import Iterator

    from egregora.data_primitives.document import Document, DocumentType

# Constants
ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)
FILENAME_PARTS_WITH_EXTENSION = 2  # Parts when splitting filename by "." (name, extension)


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


class BaseOutputSink(OutputSink, ABC):
    """Abstract base class for output formats focused on document IO.

    Output formats are responsible for persisting ``Document`` instances and
    returning them to the pipeline. Implements the OutputSink protocol.
    """

    @abstractmethod
    def persist(self, document: Document) -> None:
        """Persist a document so it becomes available at its canonical path."""

    @abstractmethod
    def get(self, doc_type: DocumentType, identifier: str) -> Document:
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
    def get_markdown_extensions(self) -> builtins.list[str]:
        """Get list of supported markdown extensions for this format."""

    @abstractmethod
    def get_format_instructions(self) -> str:
        """Generate format-specific instructions for the writer agent."""

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """Iterate through available documents, optionally filtering by ``doc_type``."""
        docs_iter = self.documents()
        if doc_type:
            # Filter documents by type if requested
            docs_iter = (d for d in docs_iter if d.type == doc_type)

        for document in docs_iter:
            identifier = document.metadata.get("storage_identifier")
            if not identifier:
                identifier = document.suggested_path
            if not identifier:
                continue

            yield DocumentMetadata(identifier=identifier, doc_type=document.type, metadata=document.metadata)

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
    ) -> builtins.list[dict[str, Any]]:
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

    @staticmethod
    def normalize_slug(slug: str) -> str:
        """Normalize slug to be URL-safe and filesystem-safe."""
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

        raise FilenameGenerationError(filename_pattern, max_attempts)

    def parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """Parse frontmatter from markdown content."""
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
            raise FrontmatterParsingError(str(e)) from e

        return metadata, body

    def prepare_window(
        self, window_label: str, _window_data: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Pre-processing hook called before writer agent processes a window."""
        # Base implementation does nothing - subclasses override for specific tasks
        return None

    def finalize_window(
        self,
        window_label: str,
        _posts_created: builtins.list[str],
        profiles_updated: builtins.list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Post-processing hook called after writer agent completes a window."""
        # Base implementation does nothing - subclasses override for specific tasks


class OutputSinkRegistry:
    """Registry for managing available output formats."""

    def __init__(self) -> None:
        self._formats: dict[str, type[BaseOutputSink]] = {}

    def register(self, format_class: type[BaseOutputSink]) -> None:
        """Register an output format class."""
        # Create temporary instance to get format_type.
        # This assumes __init__ takes no arguments, which is true for concrete adapters.
        # However, abstract OutputAdapter cannot be instantiated.
        # We assume concrete implementations are registered.
        # To fix type error, we cast format_class to Callable[[], OutputAdapter] implicitly
        instance = format_class()
        self._formats[instance.format_type] = format_class

    def get_format(self, format_type: str) -> BaseOutputSink:
        """Get an output format by type."""
        if format_type not in self._formats:
            available = ", ".join(self._formats.keys())
            msg = f"Output format '{format_type}' not found. Available: {available}"
            raise KeyError(msg)
        # Instantiate the class. Assumes no-arg constructor for initial creation.
        return self._formats[format_type]()

    def detect_format(self, site_root: Path) -> BaseOutputSink | None:
        """Auto-detect the appropriate output format for a given site."""
        for format_class in self._formats.values():
            instance = format_class()
            if instance.supports_site(site_root):
                return instance
        raise AdapterNotDetectedError(str(site_root))

    def list_formats(self) -> list[str]:
        """List all registered output format types."""
        return list(self._formats.keys())


def create_output_registry() -> OutputSinkRegistry:
    """Create a fresh output adapter registry."""
    return OutputSinkRegistry()


def create_output_sink(
    site_root: Path,
    format_type: str = "mkdocs",
    *,
    registry: OutputSinkRegistry | None = None,
) -> BaseOutputSink:
    """Create and initialize a BaseOutputSink based on configuration."""
    if registry is None:
        raise RegistryNotProvidedError

    output_sink = registry.get_format(format_type)
    output_sink.initialize(site_root)

    return output_sink
