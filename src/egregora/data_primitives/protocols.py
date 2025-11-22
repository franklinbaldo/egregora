"""Protocols that define storage and URL contracts for output adapters."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
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
    """Lightweight description of a document available in an output sink."""

    identifier: str
    doc_type: DocumentType | None
    metadata: dict[str, object]


class UrlConvention(Protocol):
    """Contract for deterministic URL generation strategies."""

    @property
    def name(self) -> str:
        """Return a short identifier describing the convention."""

    @property
    def version(self) -> str:
        """Return a semantic version or timestamp string for compatibility checks."""

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Calculate the canonical URL for ``document`` within ``ctx``."""


class OutputSink(Protocol):
    """Pure data interface for persisting and retrieving ``Document`` objects."""

    @property
    def url_convention(self) -> UrlConvention:
        """Return the URL convention adopted by this sink."""

    def persist(self, document: Document) -> None:
        """Persist ``document`` so that it becomes available at its canonical URL."""

    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a single document by its ``doc_type`` primary identifier."""

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """Iterate through available documents, optionally filtering by ``doc_type``."""

    def documents(self) -> Iterator[Document]:
        """Return all managed documents as ``Document`` objects (lazy iterator)."""


class SiteScaffolder(Protocol):
    """Lifecycle interface for adapters that manage local filesystem scaffolding."""

    def scaffold(self, path: Path, config: dict) -> None:
        """Initialize directory structure, config files, and assets."""

    def validate_structure(self, path: Path) -> bool:
        """Return ``True`` when ``path`` appears to be a valid site for this adapter."""


# Backwards compatibility while callers migrate to ``OutputSink``
OutputAdapter = OutputSink
