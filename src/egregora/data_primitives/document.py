"""Content-addressed document abstraction.

Documents represent all content produced by the Egregora pipeline (posts, profiles,
journals, enrichments). They use content-addressed IDs (UUID v5 of content hash)
for deterministic identity and deduplication.

Core has no opinions about storage - output formats decide paths and filenames.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid5

from egregora.utils.paths import slugify as _slugify

# Well-known namespace for Egregora documents
# Based on DNS namespace but specific to Egregora
NAMESPACE_DOCUMENT = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class DocumentType(Enum):
    """Types of documents in the Egregora pipeline.

    Each document type represents a distinct kind of content that may have
    different storage conventions in different output formats.
    """

    POST = "post"  # Blog posts
    PROFILE = "profile"  # Author profiles (Egregora writing ABOUT authors)
    ANNOUNCEMENT = "announcement"  # System events (/egregora commands)
    JOURNAL = "journal"  # Agent execution journals
    ENRICHMENT_URL = "enrichment_url"  # URL descriptions
    ENRICHMENT_MEDIA = "enrichment_media"  # Media file descriptions
    MEDIA = "media"  # Downloaded media files (images, videos, audio)
    ANNOTATION = "annotation"  # Conversation annotations captured during writing


@dataclass(frozen=True, slots=True)
class Document:
    r"""Content-addressed document produced by the pipeline.

    Core abstraction for all generated content.

    V3 CHANGE (2025-11-28): Adopts "Semantic Identity".
    - Posts: ID = Slug
    - Media: ID = Semantic Slug
    - Others: ID = UUID (or specific logic)

    Examples:
        >>> # Create a post document with semantic ID
        >>> doc = Document(
        ...     content="# My Post...",
        ...     type=DocumentType.POST,
        ...     metadata={"slug": "my-post"},
        ... )
        >>> doc.document_id
        'my-post'

        >>> # Create a profile (still uses UUID)
        >>> doc = Document(
        ...     content="...",
        ...     type=DocumentType.PROFILE,
        ...     id="abc-123", # Explicit ID
        ... )
        >>> doc.document_id
        'abc-123'

    Attributes:
        content: Markdown (str) or binary (bytes) content of the document
        type: Type of document (post, profile, journal, enrichment, media)
        metadata: Format-agnostic metadata (title, date, author, etc.)
        id: Explicit ID override (Semantic Identity)
        parent_id: Document ID of parent (for enrichments)
        parent: Optional in-memory parent Document reference
        created_at: Timestamp when document was created
        source_window: Window label if from windowed pipeline
        suggested_path: Optional hint for output format (not authoritative)

    """

    # Core identity
    content: str | bytes
    type: DocumentType

    # Metadata (format-agnostic)
    metadata: dict[str, Any] = field(default_factory=dict)

    # V3: Explicit ID (Semantic Identity)
    id: str | None = field(default=None)

    # Parent relationship (for enrichments)
    parent_id: str | None = None
    parent: Document | None = field(default=None, repr=False, compare=False)

    # Provenance
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_window: str | None = None

    # Hints for output formats (optional, not authoritative)
    suggested_path: str | None = None

    @property
    def document_id(self) -> str:
        """Return the document's stable identifier.

        Strategy (V3):
        1. Explicit ID (self.id)
        2. Semantic Slug (for POST/MEDIA if present)
        3. Content-based UUIDv5 (Fallback)
        """
        # 1. Explicit ID
        if self.id:
            return self.id

        # 2. Semantic Identity (Slug)
        # Only for Posts and Media, as per V3 spec
        if self.type in (DocumentType.POST, DocumentType.MEDIA):
            # Do NOT call self.slug property here to avoid recursion fallback loop
            meta_slug = self.metadata.get("slug")
            if meta_slug and isinstance(meta_slug, str) and meta_slug.strip():
                return _slugify(meta_slug.strip(), max_len=60)

        # 3. Fallback: Content-addressed UUIDv5
        if isinstance(self.content, bytes):
            payload = self.content
        else:
            payload = self.content.encode("utf-8")
        content_hash = hashlib.sha256(payload).hexdigest()
        return str(uuid5(NAMESPACE_DOCUMENT, content_hash))

    @property
    def slug(self) -> str:
        """Return a human-friendly identifier when available."""
        slug_value = self.metadata.get("slug")
        if isinstance(slug_value, str) and slug_value.strip():
            cleaned = _slugify(slug_value.strip(), max_len=60)
            if cleaned:
                return cleaned

        # Fallback: if we have an explicit ID, use it (it might be a slug)
        if self.id:
            return self.id

        # Fallback: calculate hash-based ID and take first 8 chars
        # We manually calculate UUID to avoid recursion
        if isinstance(self.content, bytes):
            payload = self.content
        else:
            payload = self.content.encode("utf-8")
        content_hash = hashlib.sha256(payload).hexdigest()
        return str(uuid5(NAMESPACE_DOCUMENT, content_hash))[:8]

    def with_parent(self, parent: Document | str) -> Document:
        """Return new document with parent relationship."""
        parent_id = parent.document_id if isinstance(parent, Document) else parent
        parent_obj = parent if isinstance(parent, Document) else self.parent
        cls = self.__class__
        return cls(
            content=self.content,
            type=self.type,
            metadata=self.metadata.copy(),
            id=self.id,
            parent_id=parent_id,
            parent=parent_obj,
            created_at=self.created_at,
            source_window=self.source_window,
            suggested_path=self.suggested_path,
        )

    def with_metadata(self, **updates: Any) -> Document:
        """Return new document with updated metadata."""
        new_metadata = self.metadata.copy()
        new_metadata.update(updates)
        cls = self.__class__
        return cls(
            content=self.content,
            type=self.type,
            metadata=new_metadata,
            id=self.id,
            parent_id=self.parent_id,
            parent=self.parent,
            created_at=self.created_at,
            source_window=self.source_window,
            suggested_path=self.suggested_path,
        )


@dataclass
class DocumentCollection:
    """Batch of documents produced by a single operation (e.g., one window)."""

    documents: list[Document]
    window_label: str | None = None

    def by_type(self, doc_type: DocumentType) -> list[Document]:
        return [doc for doc in self.documents if doc.type == doc_type]

    def find_children(self, parent_id: str) -> list[Document]:
        return [doc for doc in self.documents if doc.parent_id == parent_id]

    def find_by_id(self, document_id: str) -> Document | None:
        for doc in self.documents:
            if doc.document_id == document_id:
                return doc
        return None

    def __len__(self) -> int:
        return len(self.documents)

    def __iter__(self) -> Iterator[Document]:
        return iter(self.documents)


@dataclass(frozen=True, slots=True)
class MediaAsset(Document):
    r"""Specialized Document for binary media assets managed by the pipeline."""

    def __post_init__(self) -> None:
        if self.type != DocumentType.MEDIA:
            msg = f"MediaAsset must have type MEDIA, got {self.type}"
            raise ValueError(msg)
