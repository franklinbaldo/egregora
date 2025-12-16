"""Abstract base class for output formats (MkDocs, Hugo, Jekyll, etc.)."""

from __future__ import annotations

import datetime
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import ibis.expr.datatypes as dt
import yaml

from egregora.data_primitives import DocumentMetadata, OutputSink, UrlConvention
from egregora.data_primitives.document import Document, DocumentType
from egregora.utils import safe_path_join, slugify

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


class BaseOutputSink(OutputSink, ABC):
    """Abstract base class for output formats focused on document IO.

    Output formats are responsible for persisting ``Document`` instances and
    returning them to the pipeline. Implements the OutputSink protocol.
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

    def list_documents(self, doc_type: DocumentType | None = None) -> Table:
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
    def initialize(self, site_root: Path) -> None:
        """Initialize internal state for a specific site."""

    def parse_frontmatter(self, content: str) -> tuple[dict, str]:
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
            msg = f"Invalid YAML frontmatter: {e}"
            raise ValueError(msg) from e

        return metadata, body

    def finalize_window(
        self,
        window_label: str,
        posts_created: list[str],
        profiles_updated: list[str],
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
        instance = format_class()  # type: ignore[abstract]
        self._formats[instance.format_type] = format_class

    def get_format(self, format_type: str) -> BaseOutputSink:
        """Get an output format by type."""
        if format_type not in self._formats:
            available = ", ".join(self._formats.keys())
            msg = f"Output format '{format_type}' not found. Available: {available}"
            raise KeyError(msg)
        # Instantiate the class. Assumes no-arg constructor for initial creation.
        return self._formats[format_type]()  # type: ignore[abstract]

    def detect_format(self, site_root: Path) -> BaseOutputSink | None:
        """Auto-detect the appropriate output format for a given site."""
        for format_class in self._formats.values():
            instance = format_class()  # type: ignore[abstract]
            if instance.supports_site(site_root):
                return instance
        return None


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
        msg = "An OutputSinkRegistry instance must be provided to create output formats."
        raise ValueError(msg)

    output_format = registry.get_format(format_type)
    output_format.initialize(site_root)

    return output_format
