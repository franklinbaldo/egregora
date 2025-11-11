"""Legacy storage adapter for backward compatibility.

Adapts old PostStorage/ProfileStorage/JournalStorage protocols to work with
the new Document abstraction. This enables gradual migration without breaking
existing code.

This adapter will be removed once all consumers migrate to DocumentStorage.
"""

from __future__ import annotations

from pathlib import Path

from egregora.core.document import Document, DocumentType
from egregora.storage import JournalStorage, PostStorage, ProfileStorage


class LegacyStorageAdapter:
    """Adapter: Makes old storage protocols work with Document abstraction.

    This adapter allows the writer agent to produce Documents while still
    using the old PostStorage/ProfileStorage/JournalStorage protocols under
    the hood. Once all code migrates to DocumentStorage, this adapter can
    be removed.

    Examples:
        >>> # Old storage protocols
        >>> post_storage = MkDocsPostStorage(site_root)
        >>> profile_storage = MkDocsProfileStorage(site_root)
        >>> journal_storage = MkDocsJournalStorage(site_root)
        >>>
        >>> # Wrap in adapter
        >>> adapter = LegacyStorageAdapter(
        ...     post_storage=post_storage,
        ...     profile_storage=profile_storage,
        ...     journal_storage=journal_storage,
        ... )
        >>>
        >>> # Now use with Documents
        >>> doc = Document(content="...", type=DocumentType.POST, metadata={...})
        >>> doc_id = adapter.add(doc)

    """

    def __init__(
        self,
        post_storage: PostStorage,
        profile_storage: ProfileStorage,
        journal_storage: JournalStorage,
        site_root: Path | None = None,
    ) -> None:
        """Initialize legacy storage adapter.

        Args:
            post_storage: Old post storage protocol
            profile_storage: Old profile storage protocol
            journal_storage: Old journal storage protocol
            site_root: Optional site root for path resolution

        """
        self.post_storage = post_storage
        self.profile_storage = profile_storage
        self.journal_storage = journal_storage
        self.site_root = site_root

    def add(self, document: Document) -> str:
        """Store document using old storage protocols.

        Args:
            document: Content-addressed document

        Returns:
            Document ID (content hash)

        Raises:
            ValueError: If document type is unsupported

        """
        if document.type == DocumentType.POST:
            # Extract slug and metadata
            slug = document.metadata.get("slug", document.document_id[:8])
            metadata = document.metadata

            # Call old PostStorage.write()
            self.post_storage.write(slug=slug, metadata=metadata, content=document.content)

        elif document.type == DocumentType.PROFILE:
            # Extract author_uuid
            author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
            if not author_uuid:
                msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
                raise ValueError(msg)

            # Call old ProfileStorage.write()
            self.profile_storage.write(author_uuid=author_uuid, content=document.content)

        elif document.type == DocumentType.JOURNAL:
            # Extract window_label
            window_label = document.metadata.get("window_label", document.source_window or "unlabeled")

            # Call old JournalStorage.write()
            self.journal_storage.write(window_label=window_label, content=document.content)

        else:
            msg = f"Unsupported document type for legacy storage: {document.type}"
            raise ValueError(msg)

        return document.document_id

    def get(self, document_id: str) -> Document | None:
        """Retrieve document by ID.

        Note: Legacy storage doesn't support content-addressed lookups,
        so this method always returns None. Full DocumentStorage
        implementations (like MkDocsDocumentStorage) provide real get().

        Args:
            document_id: Content-addressed document ID

        Returns:
            None (legacy storage doesn't support retrieval)

        """
        return None

    def exists(self, document_id: str) -> bool:
        """Check if document exists.

        Note: Legacy storage doesn't support content-addressed lookups,
        so this method always returns False.

        Args:
            document_id: Content-addressed document ID

        Returns:
            False (legacy storage doesn't support existence checks)

        """
        return False

    def list_by_type(self, doc_type: DocumentType) -> list[Document]:
        """List all documents of given type.

        Note: Legacy storage doesn't support listing, so this returns empty list.

        Args:
            doc_type: Type of documents to list

        Returns:
            Empty list (legacy storage doesn't support listing)

        """
        return []

    def find_children(self, parent_id: str) -> list[Document]:
        """Find all enrichments for a parent document.

        Note: Legacy storage doesn't support parent relationships,
        so this returns empty list.

        Args:
            parent_id: Document ID of parent

        Returns:
            Empty list (legacy storage doesn't support parent relationships)

        """
        return []

    def delete(self, document_id: str) -> bool:
        """Delete document by ID.

        Note: Legacy storage doesn't support content-addressed deletion,
        so this method always returns False.

        Args:
            document_id: Content-addressed document ID

        Returns:
            False (legacy storage doesn't support deletion)

        """
        return False
