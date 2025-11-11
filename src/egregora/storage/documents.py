"""Document storage protocol.

Storage interface for content-addressed documents. Output formats implement
this protocol to decide storage paths, filenames, and format-specific behaviors
(frontmatter, registry updates, etc.).

Core pipeline only works with Document objects - no filesystem knowledge.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from egregora.core.document import Document, DocumentType


@runtime_checkable
class DocumentStorage(Protocol):
    r"""Storage interface for content-addressed documents.

    Output formats implement this protocol to decide storage conventions.
    Core pipeline has no opinions about paths, filenames, or file formats.

    Contract:
        - add() is idempotent (same document_id overwrites)
        - document_id is content-addressed (same content → same ID)
        - get() returns None if document doesn't exist
        - Implementation decides all storage details:
          * Where to save (path)
          * What filename to use
          * Whether to add frontmatter
          * Whether to update registries (.authors.yml, etc.)

    Examples:
        >>> # MkDocs implementation
        >>> storage = MkDocsDocumentStorage(site_root=Path("output"))
        >>> doc = Document(
        ...     content="# My Post\\n\\nContent...",
        ...     type=DocumentType.POST,
        ...     metadata={"title": "My Post", "date": "2025-01-10"},
        ... )
        >>> doc_id = storage.add(doc)
        >>> # MkDocs decides: output/posts/2025-01-10-my-post.md

        >>> # Hugo implementation (different conventions)
        >>> storage = HugoDocumentStorage(site_root=Path("site"))
        >>> doc_id = storage.add(doc)
        >>> # Hugo decides: site/content/posts/my-post/index.md

    """

    def add(self, document: Document) -> str:
        """Store document. Returns document_id.

        Implementation decides:
        - Where to save (path based on document type)
        - What filename to use (slug, UUID, content hash)
        - Whether to add frontmatter (YAML, TOML, JSON)
        - Whether to update registries (.authors.yml, etc.)
        - Whether to normalize slugs or add collision suffixes

        Args:
            document: Content-addressed document to store

        Returns:
            Document ID (content hash)

        Examples:
            >>> doc = Document(content="...", type=DocumentType.POST)
            >>> doc_id = storage.add(doc)
            >>> doc_id == doc.document_id
            True

        """
        ...

    def get(self, document_id: str) -> Document | None:
        """Retrieve document by content-addressed ID.

        Args:
            document_id: Content-addressed document ID (UUID v5 of content hash)

        Returns:
            Document if found, None otherwise

        Note:
            Implementation must reconstruct Document from stored format.
            This may require parsing frontmatter, loading metadata, etc.

        """
        ...

    def exists(self, document_id: str) -> bool:
        """Check if document exists.

        Args:
            document_id: Content-addressed document ID

        Returns:
            True if document exists, False otherwise

        """
        ...

    def list_by_type(self, doc_type: DocumentType) -> list[Document]:
        """List all documents of given type.

        Args:
            doc_type: Type of documents to list

        Returns:
            List of documents of the specified type

        Examples:
            >>> posts = storage.list_by_type(DocumentType.POST)
            >>> all(doc.type == DocumentType.POST for doc in posts)
            True

        """
        ...

    def find_children(self, parent_id: str) -> list[Document]:
        """Find all enrichments for a parent document.

        Useful for finding URL/media enrichments associated with a media file.

        Args:
            parent_id: Document ID of parent

        Returns:
            List of documents with matching parent_id

        Examples:
            >>> media_doc = Document(content="...", type=DocumentType.MEDIA)
            >>> enrichment = Document(
            ...     content="Description...",
            ...     type=DocumentType.ENRICHMENT_URL,
            ...     parent_id=media_doc.document_id,
            ... )
            >>> storage.add(media_doc)
            >>> storage.add(enrichment)
            >>> children = storage.find_children(media_doc.document_id)
            >>> len(children)
            1

        """
        ...

    def delete(self, document_id: str) -> bool:
        """Delete document by ID.

        Args:
            document_id: Content-addressed document ID

        Returns:
            True if document was deleted, False if it didn't exist

        Note:
            Implementation should handle cascading deletes for enrichments
            if deleting a parent document.

        """
        ...


@runtime_checkable
class DocumentIndex(Protocol):
    """Optional index for fast document lookups.

    Storage implementations can optionally provide an index for efficient
    queries. This is useful for large sites with thousands of documents.

    The index maps content-addressed IDs to storage paths, avoiding the need
    to scan the filesystem for every lookup.
    """

    def build_index(self) -> int:
        """Build or rebuild the document index.

        Scans storage to build mapping of document_id → storage_path.

        Returns:
            Number of documents indexed

        """
        ...

    def lookup(self, document_id: str) -> str | None:
        """Look up storage path for document.

        Args:
            document_id: Content-addressed document ID

        Returns:
            Storage path if document exists in index, None otherwise

        """
        ...

    def invalidate(self, document_id: str) -> None:
        """Invalidate index entry for document.

        Args:
            document_id: Content-addressed document ID

        """
        ...
