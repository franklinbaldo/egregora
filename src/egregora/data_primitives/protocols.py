"""Protocols for working with documents.

This module defines the foundational protocol interfaces for document persistence
and URL generation. These are Layer 1 abstractions that belong with other data
primitives like Document and DocumentType.

Protocols:
- OutputAdapter: Protocol for persisting documents to various backends
- UrlConvention: Protocol for generating canonical URLs for documents
- UrlContext: Context dataclass for URL generation

These protocols enable backend-agnostic document handling throughout the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document, DocumentType


@dataclass(frozen=True, slots=True)
class UrlContext:
    """Context for URL generation.

    Provides environment information needed to generate URLs (base URL, paths, locale).
    Immutable to ensure deterministic URL generation.
    """

    base_url: str = ""
    """Base URL for the site (e.g., 'https://example.com' or '')."""

    site_prefix: str = ""
    """Optional path prefix for the site (e.g., '/blog')."""

    base_path: Path | None = None
    """Optional base filesystem path (for formats that need it)."""

    locale: str | None = None
    """Optional locale for internationalized URLs (e.g., 'en', 'pt-BR')."""


class UrlConvention(Protocol):
    """Protocol for URL conventions.

    Defines how documents are mapped to canonical URLs. Implementations must be:
    - **Deterministic**: Same document always produces same URL
    - **Stable**: Re-generating doesn't change URL (no timestamps, random IDs, etc.)
    - **Pure**: No I/O, no side effects, just URL calculation

    Conventions are identified by name/version for compatibility checking.
    """

    @property
    def name(self) -> str:
        """Convention identifier (e.g., 'legacy-mkdocs', 'flat', 'hugo-like').

        Used to verify Core and OutputAdapter use the same convention.
        """
        ...

    @property
    def version(self) -> str:
        """Convention version (e.g., 'v1', '2024-01', 'latest').

        Used for compatibility checking and future migrations.
        """
        ...

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Generate canonical URL for a document.

        Must be deterministic and stable:
        - Same document + context -> same URL
        - No random components, no timestamps (unless from document metadata)
        - URL should not change on re-generation

        Args:
            document: The document to generate URL for
            ctx: Context with base URL, paths, locale, etc.

        Returns:
            Canonical URL as string (e.g., '/posts/2025-01-11-my-post/')

        Examples:
            >>> ctx = UrlContext(base_url="https://example.com")
            >>> convention.canonical_url(post_doc, ctx)
            'https://example.com/posts/2025-01-11-my-post/'

        """
        ...


class OutputAdapter(Protocol):
    """Protocol for output format implementations.

    Handles document persistence at URLs defined by a UrlConvention.
    The format adopts a convention (shared with Core) and ensures documents
    are available at the URLs that convention generates.

    Backend-agnostic: implementations can use any storage mechanism (filesystem,
    database, object storage, CMS API, etc.). Core never sees implementation details.

    Key design: Format does NOT return URLs to Core. Core calculates URLs
    independently using the same convention. This achieves perfect separation.

    Phase 6: Now supports reading documents in addition to writing.
    """

    @property
    def url_convention(self) -> UrlConvention:
        """The URL convention this format uses.

        Must match Core's convention (verified by name/version at startup).
        Both Core and Format calculate URLs independently using this convention.

        Returns:
            The UrlConvention instance used by this format

        Examples:
            >>> format.url_convention.name
            'legacy-mkdocs'
            >>> format.url_convention.version
            'v1'

        """
        ...

    def serve(self, document: Document) -> None:
        """Ensure document is served at the URL defined by url_convention.

        Does NOT return URL (Core calculates URL independently).
        Does NOT return status (idempotency is internal concern).

        Internally:
        1. Calculates URL using self.url_convention.canonical_url()
        2. Converts URL to backend-specific location (path, key, ID, etc.)
        3. Persists document (write file, save to DB, upload, queue, etc.)
        4. Handles idempotency, collisions, versioning internally

        Strategy (synchronous/asynchronous/batch/lazy) is format's choice.
        Core never knows HOW persistence happens, only requests it.

        Args:
            document: The document to serve

        Examples:
            >>> # Core flow
            >>> url = url_convention.canonical_url(document, ctx)  # Core calculates
            >>> output_format.serve(document)  # Format persists (fire-and-forget)
            >>> # Use url in content, cross-refs, etc.

        Note:
            This method should be idempotent: calling it multiple times with the
            same document should be a safe no-op (no errors, no duplicates).

        """
        ...

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Read document by type and primary identifier.

        Phase 6: Added to enable reading documents without direct filesystem access.

        Args:
            doc_type: Type of document (POST, PROFILE, JOURNAL, etc.)
            identifier: Primary identifier for the document:
                - PROFILE: author UUID (e.g., "abc-123-uuid")
                - POST: slug (e.g., "my-post")
                - JOURNAL: window label (e.g., "2025-01-11 10:00 to 12:00")
                - ENRICHMENT_URL: URL or slug
                - ENRICHMENT_MEDIA: media filename
                - MEDIA: media filename

        Returns:
            Document if found, None if not found

        Examples:
            >>> # Read profile by UUID
            >>> doc = output_format.read_document(DocumentType.PROFILE, "abc-123-uuid")
            >>> if doc:
            ...     print(doc.content)
            ...     print(doc.metadata)

            >>> # Read post by slug
            >>> doc = output_format.read_document(DocumentType.POST, "my-post")

        Note:
            For documents identified by multiple fields (e.g., posts by slug+date),
            implementations may need to use heuristics (e.g., return most recent post
            with that slug). For precise lookups, consider using read_by_url() if added.

        """
        ...

    def list_documents(self, doc_type: DocumentType | None = None) -> list[Document]:
        """List all documents, optionally filtered by type.

        Phase 6: Added to enable listing documents without direct filesystem access.

        Args:
            doc_type: Optional document type filter. If None, returns all documents.

        Returns:
            List of documents, may be empty if no documents found.

        Examples:
            >>> # List all profiles
            >>> profiles = output_format.list_documents(DocumentType.PROFILE)
            >>> for profile in profiles:
            ...     print(f"{profile.metadata.get('uuid')}: {profile.metadata.get('name')}")

            >>> # List all documents
            >>> all_docs = output_format.list_documents()
            >>> print(f"Total documents: {len(all_docs)}")

        Note:
            This method may be expensive for large document sets.
            Implementations should consider caching or pagination if needed.

        """
        ...
