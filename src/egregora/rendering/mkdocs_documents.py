"""MkDocs-specific document storage implementation.

Implements DocumentStorage protocol with MkDocs conventions:
- Posts: posts/{date}-{slug}.md with YAML frontmatter
- Profiles: profiles/{uuid}.md with YAML frontmatter + .authors.yml update
- Journals: posts/journal/journal_{label}.md with YAML frontmatter
- URL enrichments: docs/media/urls/{doc_id}.md (content-addressed)
- Media enrichments: docs/media/{filename}.md
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from egregora.agents.shared.profiler import write_profile as write_profile_content
from egregora.core.document import Document, DocumentType

logger = logging.getLogger(__name__)


class MkDocsDocumentStorage:
    r"""MkDocs-specific document storage with opinionated conventions.

    Storage paths by document type:
        POST:              posts/{date}-{slug}.md
        PROFILE:           profiles/{uuid}.md + .authors.yml
        JOURNAL:           posts/journal/journal_{label}.md
        ENRICHMENT_URL:    docs/media/urls/{doc_id}.md (content-addressed)
        ENRICHMENT_MEDIA:  docs/media/{filename}.md
        MEDIA:             docs/media/{filename}

    All documents get YAML frontmatter except URL enrichments (plain markdown).
    Profiles trigger .authors.yml updates for MkDocs blog plugin.

    Examples:
        >>> storage = MkDocsDocumentStorage(site_root=Path("output"))
        >>> doc = Document(
        ...     content="# My Post\\n\\nContent...",
        ...     type=DocumentType.POST,
        ...     metadata={"title": "My Post", "date": "2025-01-10", "slug": "my-post"},
        ... )
        >>> doc_id = storage.add(doc)
        >>> # Writes to: output/posts/2025-01-10-my-post.md

    """

    def __init__(self, site_root: Path) -> None:
        """Initialize MkDocs document storage.

        Args:
            site_root: Root directory for MkDocs site

        Side Effects:
            Creates necessary directories (posts, profiles, docs/media/urls)

        """
        self.site_root = site_root
        self.posts_dir = site_root / "posts"
        self.profiles_dir = site_root / "profiles"
        self.journal_dir = site_root / "posts" / "journal"
        self.urls_dir = site_root / "docs" / "media" / "urls"
        self.media_dir = site_root / "docs" / "media"

        # Create directories
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.urls_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

        # Index: document_id → storage_path (for fast lookups)
        self._index: dict[str, Path] = {}

    def add(self, document: Document) -> str:
        """Store document in MkDocs-specific location.

        Idempotent: If document_id already exists, overwrites at the same path.

        Args:
            document: Content-addressed document

        Returns:
            Document ID (content hash)

        Raises:
            ValueError: If document type is unknown

        """
        doc_id = document.document_id

        # Check if document already exists (idempotency)
        if doc_id in self._index:
            existing_path = self._index[doc_id]
            logger.debug("Document %s already exists at %s, overwriting (idempotent)", doc_id, existing_path)
            # Overwrite at existing path
            path = existing_path
        else:
            # New document - determine storage path
            if document.type == DocumentType.POST:
                path = self._determine_post_path(document)
            elif document.type == DocumentType.PROFILE:
                path = self._determine_profile_path(document)
            elif document.type == DocumentType.JOURNAL:
                path = self._determine_journal_path(document)
            elif document.type == DocumentType.ENRICHMENT_URL:
                path = self._determine_url_enrichment_path(document)
            elif document.type == DocumentType.ENRICHMENT_MEDIA:
                path = self._determine_media_enrichment_path(document)
            elif document.type == DocumentType.MEDIA:
                path = self._determine_media_path(document)
            else:
                msg = f"Unknown document type: {document.type}"
                raise ValueError(msg)

        # Write document at determined path
        self._write_document(document, path)

        # Update index
        self._index[doc_id] = path

        logger.debug("Stored document %s at %s", doc_id, path)
        return doc_id

    def get(self, document_id: str) -> Document | None:
        """Retrieve document by ID.

        Args:
            document_id: Content-addressed document ID

        Returns:
            Document if found, None otherwise

        """
        # Try index lookup first
        if document_id in self._index:
            path = self._index[document_id]
            if path.exists():
                return self._load_document(path)

        # Fall back to scanning (index may be stale)
        for path in self._scan_all_documents():
            doc = self._load_document(path)
            if doc and doc.document_id == document_id:
                # Update index
                self._index[document_id] = path
                return doc

        return None

    def exists(self, document_id: str) -> bool:
        """Check if document exists.

        Args:
            document_id: Content-addressed document ID

        Returns:
            True if document exists

        """
        return self.get(document_id) is not None

    def list_by_type(self, doc_type: DocumentType) -> list[Document]:
        """List all documents of given type.

        Args:
            doc_type: Type of documents to list

        Returns:
            List of documents

        """
        documents = []
        for path in self._scan_documents_by_type(doc_type):
            doc = self._load_document(path)
            if doc and doc.type == doc_type:
                documents.append(doc)
        return documents

    def find_children(self, parent_id: str) -> list[Document]:
        """Find all enrichments for a parent document.

        Args:
            parent_id: Document ID of parent

        Returns:
            List of enrichment documents

        """
        children = []
        # Scan enrichment directories
        for enrichment_path in self.urls_dir.glob("*.md"):
            doc = self._load_document(enrichment_path)
            if doc and doc.parent_id == parent_id:
                children.append(doc)

        for enrichment_path in self.media_dir.rglob("*.md"):
            if enrichment_path.parent == self.urls_dir:
                continue  # Already scanned
            doc = self._load_document(enrichment_path)
            if doc and doc.parent_id == parent_id:
                children.append(doc)

        return children

    def delete(self, document_id: str) -> bool:
        """Delete document by ID.

        Args:
            document_id: Content-addressed document ID

        Returns:
            True if deleted, False if not found

        """
        if document_id in self._index:
            path = self._index[document_id]
            if path.exists():
                path.unlink()
                del self._index[document_id]
                logger.info("Deleted document %s", document_id)
                return True

        # Fall back to scanning
        for path in self._scan_all_documents():
            doc = self._load_document(path)
            if doc and doc.document_id == document_id:
                path.unlink()
                if document_id in self._index:
                    del self._index[document_id]
                logger.info("Deleted document %s", document_id)
                return True

        return False

    # --- Storage helpers (one per document type) ---

    def _determine_post_path(self, document: Document) -> Path:
        """Determine storage path for post (collision-safe)."""
        # Extract metadata
        slug = document.metadata.get("slug", document.document_id[:8])
        date = document.metadata.get("date", "")

        # Normalize slug (simple implementation)
        normalized_slug = slug.lower().replace(" ", "-")
        normalized_slug = "".join(c for c in normalized_slug if c.isalnum() or c == "-")

        # Generate filename: {date}-{slug}.md
        if date:
            filename = f"{date}-{normalized_slug}.md"
        else:
            filename = f"{normalized_slug}.md"

        path = self.posts_dir / filename

        # Handle collisions by adding numeric suffix
        # Only check if path exists AND is a different document
        counter = 1
        while path.exists():
            # Check if existing file is the same document (by document_id)
            existing_doc = self._load_document(path)
            if existing_doc and existing_doc.document_id == document.document_id:
                # Same document - reuse path (idempotent)
                return path

            # Different document - add suffix
            if date:
                filename = f"{date}-{normalized_slug}-{counter}.md"
            else:
                filename = f"{normalized_slug}-{counter}.md"
            path = self.posts_dir / filename
            counter += 1

        return path

    def _write_document(self, document: Document, path: Path) -> None:
        """Write document to filesystem with appropriate format."""
        import yaml

        # Handle different document types
        if document.type in (DocumentType.POST, DocumentType.JOURNAL):
            # Write with YAML frontmatter
            yaml_front = yaml.dump(
                document.metadata, default_flow_style=False, allow_unicode=True, sort_keys=False
            )
            full_content = f"---\n{yaml_front}---\n\n{document.content}"
            path.write_text(full_content, encoding="utf-8")
        elif document.type == DocumentType.PROFILE:
            # Use write_profile_content (handles frontmatter, .authors.yml)
            author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
            write_profile_content(author_uuid, document.content, self.profiles_dir)
        elif document.type == DocumentType.ENRICHMENT_URL:
            # URL enrichment with optional frontmatter
            if document.parent_id or document.metadata:
                metadata = document.metadata.copy()
                if document.parent_id:
                    metadata["parent_id"] = document.parent_id

                yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
                full_content = f"---\n{yaml_front}---\n\n{document.content}"
                path.write_text(full_content, encoding="utf-8")
            else:
                path.write_text(document.content, encoding="utf-8")
        else:
            # Default: write content as-is (media enrichments, media files)
            path.write_text(document.content, encoding="utf-8")

    def _determine_profile_path(self, document: Document) -> Path:
        """Determine storage path for profile."""
        author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
        if not author_uuid:
            msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
            raise ValueError(msg)

        # Profile path: profiles/{uuid}.md
        return self.profiles_dir / f"{author_uuid}.md"

    def _determine_journal_path(self, document: Document) -> Path:
        """Determine storage path for journal entry."""
        window_label = document.metadata.get("window_label", document.source_window or "unlabeled")

        # Sanitize label for filename
        safe_label = window_label.replace(" ", "_").replace(":", "-")
        filename = f"journal_{safe_label}.md"
        return self.journal_dir / filename

    def _determine_url_enrichment_path(self, document: Document) -> Path:
        """Determine storage path for URL enrichment (content-addressed)."""
        # Use document_id as filename (content-addressed)
        return self.urls_dir / f"{document.document_id}.md"

    def _determine_media_enrichment_path(self, document: Document) -> Path:
        """Determine storage path for media enrichment."""
        # Use suggested filename or fall back to document_id
        filename = document.suggested_path or f"{document.document_id}.md"
        filename = filename.removeprefix("docs/media/")

        path = self.media_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _determine_media_path(self, document: Document) -> Path:
        """Determine storage path for media file."""
        filename = document.suggested_path or document.document_id
        filename = filename.removeprefix("docs/media/")

        path = self.media_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # --- Loading helpers ---

    def _load_document(self, path: Path) -> Document | None:
        """Load document from filesystem."""
        if not path.exists():
            return None

        try:
            raw_content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to read %s: %s", path, e)
            return None

        # Infer document type from path
        doc_type = self._infer_type(path)

        # Parse metadata and extract body content (without frontmatter)
        metadata, body_content = self._parse_frontmatter(raw_content)

        # Determine parent_id (if enrichment)
        parent_id = metadata.get("parent_id")

        return Document(
            content=body_content,  # Use body without frontmatter
            type=doc_type,
            metadata=metadata,
            parent_id=parent_id,
        )

    def _infer_type(self, path: Path) -> DocumentType:
        """Infer document type from storage path."""
        relative = path.relative_to(self.site_root)
        parts = relative.parts

        if parts[0] == "posts":
            if len(parts) > 1 and parts[1] == "journal":
                return DocumentType.JOURNAL
            return DocumentType.POST
        if parts[0] == "profiles":
            return DocumentType.PROFILE
        if "urls" in parts:
            return DocumentType.ENRICHMENT_URL
        if path.suffix == ".md":
            return DocumentType.ENRICHMENT_MEDIA
        return DocumentType.MEDIA

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """Parse YAML frontmatter and return (metadata, body).

        Args:
            content: Full file content with optional frontmatter

        Returns:
            Tuple of (metadata dict, body content without frontmatter)

        """
        if not content.startswith("---\n"):
            return {}, content

        try:
            import yaml

            end_marker = content.find("\n---\n", 4)
            if end_marker == -1:
                return {}, content

            frontmatter_text = content[4:end_marker]
            body = content[end_marker + 5 :].lstrip()  # Skip "\n---\n" and leading whitespace

            metadata = yaml.safe_load(frontmatter_text) or {}
            if not isinstance(metadata, dict):
                return {}, content

            return metadata, body
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to parse frontmatter: %s", e)
            return {}, content

    # --- Scanning helpers ---

    def _scan_all_documents(self) -> list[Path]:
        """Scan all document paths."""
        paths = []
        paths.extend(self.posts_dir.glob("*.md"))
        paths.extend(self.journal_dir.glob("*.md"))
        paths.extend(self.profiles_dir.glob("*.md"))
        paths.extend(self.urls_dir.glob("*.md"))
        paths.extend(self.media_dir.rglob("*"))
        return paths

    def _scan_documents_by_type(self, doc_type: DocumentType) -> list[Path]:
        """Scan paths for specific document type."""
        if doc_type == DocumentType.POST:
            return list(self.posts_dir.glob("*.md"))
        if doc_type == DocumentType.PROFILE:
            return list(self.profiles_dir.glob("*.md"))
        if doc_type == DocumentType.JOURNAL:
            return list(self.journal_dir.glob("*.md"))
        if doc_type == DocumentType.ENRICHMENT_URL:
            return list(self.urls_dir.glob("*.md"))
        if doc_type == DocumentType.ENRICHMENT_MEDIA:
            return [p for p in self.media_dir.rglob("*.md") if p.parent != self.urls_dir]
        if doc_type == DocumentType.MEDIA:
            return [p for p in self.media_dir.rglob("*") if p.suffix != ".md"]
        return []
