"""Modern, runtime-checkable protocols for data persistence and site management.

This module defines the abstract contracts for how Egregora interacts with
output formats and storage backends. It separates the behavioral interfaces
(like `OutputSink` and `SiteScaffolder`) from the concrete data structures
(like `Document`) that they operate on.

Key Protocols:
- UrlConvention: Purely logical contract for generating canonical URLs.
- OutputSink: Data plane for persisting and retrieving documents.
- SiteScaffolder: Project lifecycle management for initializing local sites.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table

    # Use a forward reference to avoid circular import
    from egregora.data_primitives.document import Document, DocumentType


@dataclass(frozen=True, slots=True)
class UrlContext:
    """Context information required when generating canonical URLs."""

    base_url: str = ""
    site_prefix: str = ""
    base_path: Path | None = None
    locale: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Lightweight description of a document available in an output sink.

    Used for efficient document enumeration without loading full content.
    Returned by OutputSink.list() for memory-efficient iteration.
    """

    identifier: str
    doc_type: DocumentType | None
    metadata: dict[str, object]


class UrlConvention(Protocol):
    """Contract for deterministic URL generation strategies.

    CRITICAL: This is a PURELY LOGICAL protocol. Implementations must:
    - Use ONLY string operations (no Path, no filesystem concepts)
    - Return URLs as strings ('/posts/foo/' or 'https://example.com/posts/foo/')
    - Have NO knowledge of filesystem layout (docs_dir, file extensions, etc.)
    """

    @property
    def name(self) -> str:
        """Return a short identifier describing the convention."""

    @property
    def version(self) -> str:
        """Return a semantic version or timestamp string for compatibility checks."""

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Calculate the canonical URL for ``document`` within ``ctx``."""


@runtime_checkable
class OutputSink(Protocol):
    """Runtime data plane for document persistence and retrieval."""

    @property
    def url_convention(self) -> UrlConvention:
        """Return the URL convention adopted by this sink."""

    @property
    def url_context(self) -> UrlContext:
        """Return the URL context for canonical URL generation."""

    def persist(self, document: Document) -> None:
        """Persist ``document`` so that it becomes available at its canonical URL."""

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a single document by its ``doc_type`` primary identifier."""

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """Iterate through available documents, optionally filtering by ``doc_type``."""

    def list_documents(self, doc_type: DocumentType | None = None) -> Table:
        """Return all known documents as an Ibis table, optionally filtered by ``doc_type``."""

    def documents(self) -> Iterator[Document]:
        """Return all managed documents as Document objects (lazy iterator)."""

    def get_format_instructions(self) -> str:
        """Get instructions on how to format content for this sink."""
        ...

    def finalize_window(
        self,
        window_label: str,
        _posts_created: list[str],
        profiles_updated: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Hook called after processing a window."""
        ...


@runtime_checkable
class SiteScaffolder(Protocol):
    """Project lifecycle management for local site initialization."""

    def scaffold_site(self, site_root: Path, site_name: str, **kwargs: object) -> tuple[Path, bool]:
        """Initialize directory structure, config files, and assets."""

    def supports_site(self, site_root: Path) -> bool:
        """Check if this scaffolder can handle the given site."""

    def resolve_paths(self, site_root: Path) -> dict[str, Any]:
        """Resolve all paths for an existing site."""


__all__ = [
    "DocumentMetadata",
    "OutputSink",
    "SiteScaffolder",
    "UrlContext",
    "UrlConvention",
]
