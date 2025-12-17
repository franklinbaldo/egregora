"""Structured metadata for publishable documents.

This module provides type-safe metadata with sensible defaults,
ensuring consistent structure across all document types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document, DocumentType

# Known fields that map to dataclass attributes
KNOWN_FIELDS = frozenset({
    "title", "slug", "date", "updated", "summary",
    "tags", "categories", "authors", "draft",
    "type", "doc_id", "source_adapter", "source_window",
})


def _get_fallback_title(doc_type: DocumentType) -> str:
    """Generate fallback title based on document type."""
    return f"Untitled {doc_type.value.capitalize()}"


@dataclass(frozen=True, slots=True)
class PublishableMetadata:
    """Structured metadata for publishable documents.

    Immutable dataclass with sensible defaults. Use `from_document()`
    to create from a Document instance, or construct directly.

    Fields are designed to support:
    - MkDocs frontmatter
    - RSS feeds
    - Sitemaps
    - Social cards
    """

    # Core identity (required)
    title: str
    slug: str

    # Timestamps (ISO 8601)
    date: str
    updated: str

    # Content metadata (with defaults)
    summary: str = ""
    tags: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    authors: tuple[str, ...] = ()

    # Publishing state
    draft: bool = False

    # Document identity
    doc_type: str = ""
    doc_id: str = ""

    # Provenance
    source_adapter: str = "unknown"
    source_window: str | None = None

    # Extension point
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_document(cls, doc: Document) -> PublishableMetadata:
        """Create PublishableMetadata from a Document.

        Extracts known fields from doc.metadata, applies defaults
        for missing values, and puts unknown fields into `extra`.
        """
        meta = doc.metadata

        # Extract or compute values
        title = meta.get("title") or _get_fallback_title(doc.type)
        slug = meta.get("slug") or doc.slug

        # Ensure date defaults are timezone-aware (assume UTC if naive)
        created_at = doc.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        date = meta.get("date") or created_at.isoformat()
        updated = meta.get("updated") or date

        # Convert lists to tuples for immutability
        tags = tuple(meta.get("tags") or [])
        categories = tuple(meta.get("categories") or [])
        authors = tuple(meta.get("authors") or [])

        # Collect extra fields
        extra = {k: v for k, v in meta.items() if k not in KNOWN_FIELDS}

        return cls(
            title=title,
            slug=slug,
            date=date,
            updated=updated,
            summary=meta.get("summary", ""),
            tags=tags,
            categories=categories,
            authors=authors,
            draft=bool(meta.get("draft", False)),
            doc_type=doc.type.value,
            doc_id=doc.document_id,
            source_adapter=meta.get("source_adapter", "unknown"),
            source_window=doc.source_window,
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for frontmatter serialization.

        - Tuples are converted to lists
        - Extra fields are merged in
        - None values may be omitted
        """
        result: dict[str, Any] = {
            "title": self.title,
            "slug": self.slug,
            "date": self.date,
            "updated": self.updated,
            "summary": self.summary,
            "tags": list(self.tags),
            "categories": list(self.categories),
            "authors": list(self.authors),
            "draft": self.draft,
            "type": self.doc_type,
            "doc_id": self.doc_id,
            "source_adapter": self.source_adapter,
        }

        if self.source_window:
            result["source_window"] = self.source_window

        # Merge extra fields
        result.update(self.extra)

        return result
