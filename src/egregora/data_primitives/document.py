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

# Well-known namespace for Egregora documents
# Based on DNS namespace but specific to Egregora
NAMESPACE_DOCUMENT = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class DocumentType(Enum):
    """Types of documents in the Egregora pipeline.

    Each document type represents a distinct kind of content that may have
    different storage conventions in different output formats.
    """

    POST = "post"  # Blog posts
    PROFILE = "profile"  # Author profiles
    JOURNAL = "journal"  # Agent execution journals
    ENRICHMENT_URL = "enrichment_url"  # URL descriptions
    ENRICHMENT_MEDIA = "enrichment_media"  # Media file descriptions
    MEDIA = "media"  # Downloaded media files (images, videos, audio)


@dataclass(frozen=True, slots=True)
class Document:
    r"""Content-addressed document produced by the pipeline.

    Core abstraction for all generated content. The document ID is deterministic
    based on content hash, enabling deduplication and cache invalidation.

    Output formats decide storage paths and filenames. Core has no opinions.

    Examples:
        >>> # Create a post document
        >>> doc = Document(
        ...     content="# My Post\n\nContent...",
        ...     type=DocumentType.POST,
        ...     metadata={"title": "My Post", "date": "2025-01-10", "slug": "my-post"},
        ... )
        >>> doc.document_id  # Content-addressed ID
        'abc123...'

        >>> # Create enrichment with parent
        >>> enrichment = Document(
        ...     content="Article summary...",
        ...     type=DocumentType.ENRICHMENT_URL,
        ...     metadata={"url": "https://example.com"},
        ...     parent_id="parent-doc-id",
        ... )
        >>> enrichment.parent_id
        'parent-doc-id'

    Attributes:
        content: Markdown content of the document
        type: Type of document (post, profile, journal, enrichment, media)
        metadata: Format-agnostic metadata (title, date, author, etc.)
        parent_id: Document ID of parent (for enrichments)
        created_at: Timestamp when document was created
        source_window: Window label if from windowed pipeline
        suggested_path: Optional hint for output format (not authoritative)

    """

    # Core identity
    content: str
    type: DocumentType

    # Metadata (format-agnostic)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Parent relationship (for enrichments)
    parent_id: str | None = None

    # Provenance
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_window: str | None = None

    # Hints for output formats (optional, not authoritative)
    suggested_path: str | None = None

    @property
    def document_id(self) -> str:
        """UUID v5 of content hash. Deterministic and deduplicatable.

        The document ID is computed from a SHA256 hash of the content,
        which is then used to generate a UUID v5. This ensures:

        1. Same content → same ID (deduplication)
        2. Content changes → ID changes (cache invalidation)
        3. Reproducibility across runs

        Returns:
            36-character UUID string

        Examples:
            >>> doc1 = Document(content="Hello", type=DocumentType.POST)
            >>> doc2 = Document(content="Hello", type=DocumentType.POST)
            >>> doc1.document_id == doc2.document_id
            True
            >>> doc3 = Document(content="World", type=DocumentType.POST)
            >>> doc1.document_id == doc3.document_id
            False

        """
        content_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return str(uuid5(NAMESPACE_DOCUMENT, content_hash))

    def with_parent(self, parent_id: str) -> Document:
        """Return new document with parent relationship.

        Useful for creating enrichments that reference parent media.

        Args:
            parent_id: Document ID of parent

        Returns:
            New Document instance with parent_id set

        Examples:
            >>> doc = Document(content="...", type=DocumentType.ENRICHMENT_URL)
            >>> enrichment = doc.with_parent("media-doc-id")
            >>> enrichment.parent_id
            'media-doc-id'

        """
        return Document(
            content=self.content,
            type=self.type,
            metadata=self.metadata.copy(),
            parent_id=parent_id,
            created_at=self.created_at,
            source_window=self.source_window,
            suggested_path=self.suggested_path,
        )

    def with_metadata(self, **updates: Any) -> Document:
        """Return new document with updated metadata.

        Args:
            **updates: Metadata fields to update

        Returns:
            New Document instance with updated metadata

        Examples:
            >>> doc = Document(
            ...     content="...",
            ...     type=DocumentType.POST,
            ...     metadata={"title": "Original"},
            ... )
            >>> updated = doc.with_metadata(title="Updated", author="Alice")
            >>> updated.metadata["title"]
            'Updated'

        """
        new_metadata = self.metadata.copy()
        new_metadata.update(updates)
        return Document(
            content=self.content,
            type=self.type,
            metadata=new_metadata,
            parent_id=self.parent_id,
            created_at=self.created_at,
            source_window=self.source_window,
            suggested_path=self.suggested_path,
        )


@dataclass
class DocumentCollection:
    """Batch of documents produced by a single operation (e.g., one window).

    Collections group related documents and provide filtering/querying methods.

    Examples:
        >>> docs = [
        ...     Document(content="Post 1", type=DocumentType.POST),
        ...     Document(content="Post 2", type=DocumentType.POST),
        ...     Document(content="Profile", type=DocumentType.PROFILE),
        ... ]
        >>> collection = DocumentCollection(documents=docs, window_label="2025-01-10")
        >>> posts = collection.by_type(DocumentType.POST)
        >>> len(posts)
        2

    Attributes:
        documents: List of documents in this collection
        window_label: Optional label for the window that produced these documents

    """

    documents: list[Document]
    window_label: str | None = None

    def by_type(self, doc_type: DocumentType) -> list[Document]:
        """Filter documents by type.

        Args:
            doc_type: Type of documents to filter

        Returns:
            List of documents matching the type

        Examples:
            >>> collection.by_type(DocumentType.POST)
            [Document(...), Document(...)]

        """
        return [doc for doc in self.documents if doc.type == doc_type]

    def find_children(self, parent_id: str) -> list[Document]:
        """Find all documents with given parent.

        Useful for finding enrichments associated with a media file.

        Args:
            parent_id: Document ID of parent

        Returns:
            List of documents with matching parent_id

        Examples:
            >>> enrichments = collection.find_children("media-doc-id")
            >>> all(e.parent_id == "media-doc-id" for e in enrichments)
            True

        """
        return [doc for doc in self.documents if doc.parent_id == parent_id]

    def find_by_id(self, document_id: str) -> Document | None:
        """Find document by ID.

        Args:
            document_id: Document ID to search for

        Returns:
            Document if found, None otherwise

        """
        for doc in self.documents:
            if doc.document_id == document_id:
                return doc
        return None

    def __len__(self) -> int:
        """Return number of documents in collection."""
        return len(self.documents)

    def __iter__(self) -> Iterator[Document]:
        """Iterate over documents."""
        return iter(self.documents)
