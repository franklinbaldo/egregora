"""Protocols that define storage and URL contracts for output adapters."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.data_primitives.document import Document, DocumentType


@dataclass(frozen=True, slots=True)
class UrlContext:
    """Context information required when generating canonical URLs."""

    base_url: str = ""
    site_prefix: str = ""
    base_path: Path | None = None
    locale: str | None = None


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


class OutputAdapter(Protocol):
    """Unified protocol for persisting and retrieving documents."""

    @property
    def url_convention(self) -> UrlConvention:
        """Return the URL convention adopted by this adapter."""

    def persist(self, document: Document) -> None:
        """Persist ``document`` so that it becomes available at its canonical URL."""

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a single document by its ``doc_type`` primary identifier."""

    def list_documents(self, doc_type: DocumentType | None = None) -> Table:
        """Return all known documents as an Ibis table, optionally filtered by ``doc_type``."""

    def documents(self) -> Iterator[Document]:
        """Return all managed documents as Document objects (lazy iterator for memory efficiency)."""

    def resolve_document_path(self, identifier: str) -> Path:
        """Resolve the given storage identifier (from ``list_documents``) to an actual filesystem path."""
