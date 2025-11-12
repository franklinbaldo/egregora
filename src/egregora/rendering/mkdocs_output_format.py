"""MkDocs output format implementation.

Implements OutputFormat protocol using filesystem-based MkDocs conventions.
Adopts LegacyMkDocsUrlConvention and ensures documents are served at those URLs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.core.document import Document
    from egregora.storage.url_convention import UrlContext, UrlConvention

# Lazy import to avoid circular dependency (mkdocs_output_format ← agents ← writer/core → mkdocs_output_format)
# from egregora.agents.shared.profiler import write_profile as write_profile_content
from egregora.core.document import DocumentType
from egregora.rendering.legacy_mkdocs_url_convention import LegacyMkDocsUrlConvention

logger = logging.getLogger(__name__)


class MkDocsOutputFormat:
    """MkDocs output format with filesystem backend.

    Adopts LegacyMkDocsUrlConvention and persists documents to filesystem.
    Core calculates URLs independently - this format just ensures documents
    are served at the expected locations.

    Backend-specific implementation:
    - Filesystem storage under site_root
    - YAML frontmatter for posts/journals/profiles
    - .authors.yml updates for profiles
    - Idempotency via document_id checking

    Examples:
        >>> convention = LegacyMkDocsUrlConvention()
        >>> ctx = UrlContext(base_url="https://example.com")
        >>> format = MkDocsOutputFormat(site_root=Path("output"), url_context=ctx)
        >>>
        >>> # Core calculates URL
        >>> url = convention.canonical_url(document, ctx)
        >>> # Format ensures document is served
        >>> format.serve(document)  # Returns nothing (void)

    """

    def __init__(self, site_root: Path, url_context: UrlContext) -> None:
        """Initialize MkDocs output format.

        Args:
            site_root: Root directory for MkDocs site
            url_context: Context for URL generation (base_url, etc.)

        Side Effects:
            Creates necessary directories

        """
        self.site_root = site_root
        self._ctx = url_context
        self._url_convention = LegacyMkDocsUrlConvention()

        # Create standard directories
        self.posts_dir = site_root / "posts"
        self.profiles_dir = site_root / "profiles"
        self.journal_dir = site_root / "posts" / "journal"
        self.urls_dir = site_root / "docs" / "media" / "urls"
        self.media_dir = site_root / "docs" / "media"

        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.urls_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

        # Index for idempotency: document_id → path
        self._index: dict[str, Path] = {}

    @property
    def url_convention(self) -> UrlConvention:
        """The URL convention this format uses.

        Returns:
            LegacyMkDocsUrlConvention instance

        """
        return self._url_convention

    def serve(self, document: Document) -> None:
        """Ensure document is served at URL defined by url_convention.

        Internally:
        1. Calculates URL using url_convention
        2. Converts URL to filesystem path
        3. Checks idempotency (same document_id at path)
        4. Writes document with appropriate format
        5. Updates index

        Slug Collision Behavior (P1 Badge - Intentional Design):
        -------------------------------------------------------
        Overwriting behavior varies by document type:

        **Posts** (slug + date based):
          - Path: `posts/YYYY-MM-DD-{slug}.md`
          - Collision: **Overwrites** (second post with same slug+date replaces first)
          - Rationale: Posts are identified by (slug, date), not content.
            Writing post "my-post" on "2025-01-11" twice should UPDATE the file,
            like UPDATE in SQL or PUT in REST. This is idempotent publishing.

        **Profiles** (UUID based):
          - Path: `profiles/{uuid}.md`
          - Collision: **Overwrites** (updating profile for same UUID)
          - Rationale: Profiles are identified by UUID. Updating a user's profile
            should replace the existing file, not create duplicates.

        **Enrichment URLs** (content-hash based):
          - Path: `enrichments/{hash}.md`
          - Collision: **Detects and resolves** with suffix (`{hash}-1.md`)
          - Rationale: Hash-based paths should be unique. A collision indicates
            either (1) true hash collision (rare) or (2) different content
            mapped to same path. Resolution adds numeric suffix.

        The current implementation returns `None` (fire-and-forget). If error
        reporting is needed in the future, the signature can be extended to
        return an optional `ServeResult` or raise exceptions.

        Args:
            document: Document to serve

        Returns:
            None (void return - fire-and-forget pattern)

        Raises:
            IOError: If filesystem write fails

        """
        doc_id = document.document_id

        # Always calculate URL and path from current metadata
        # Cannot use cached path - metadata may have changed!
        # (document_id is content-based, doesn't include slug/date changes)
        url = self._url_convention.canonical_url(document, self._ctx)
        path = self._url_to_path(url, document)

        # Check if this document was previously served at a different path
        if doc_id in self._index:
            old_path = self._index[doc_id]
            if old_path != path:
                # Metadata changed (e.g., slug/date update) - move file
                if old_path.exists():
                    logger.info("Moving document %s: %s → %s", doc_id[:8], old_path, path)
                    # Ensure new parent directory exists
                    path.parent.mkdir(parents=True, exist_ok=True)
                    # Move to new location (or will overwrite if path collision)
                    old_path.rename(path) if not path.exists() else old_path.unlink()
                else:
                    logger.debug("Old path %s doesn't exist, writing to new path %s", old_path, path)
            else:
                # Same path - true idempotent rewrite
                logger.debug("Document %s unchanged at %s (idempotent)", doc_id[:8], path)

        # For content-addressed paths, check for hash collisions
        # (slug/UUID paths are deterministic, collisions are updates not errors)
        if path.exists() and document.type == DocumentType.ENRICHMENT_URL:
            existing_doc_id = self._get_document_id_at_path(path)
            if existing_doc_id and existing_doc_id != doc_id:
                # True collision: different document at same content hash
                path = self._resolve_collision(path, doc_id)
                logger.warning("Hash collision for %s, using %s", doc_id[:8], path)

        # Write document at determined path
        self._write_document(document, path)

        # Update index
        self._index[doc_id] = path

        logger.debug("Served document %s at %s", doc_id, path)

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Read document by type and primary identifier.

        Phase 6: Enables reading documents without direct filesystem access.

        Args:
            doc_type: Type of document (POST, PROFILE, JOURNAL, etc.)
            identifier: Primary identifier (UUID for profiles, slug for posts, etc.)

        Returns:
            Document if found, None if not found

        """
        # Determine path based on document type
        path: Path | None = None

        if doc_type == DocumentType.PROFILE:
            # Profiles: identifier is author UUID
            path = self.profiles_dir / f"{identifier}.md"

        elif doc_type == DocumentType.POST:
            # Posts: identifier is slug (search for most recent with that slug)
            # For simplicity, we'll look for any post with that slug
            matching_posts = list(self.posts_dir.glob(f"*-{identifier}.md"))
            if matching_posts:
                # Return most recently modified
                path = max(matching_posts, key=lambda p: p.stat().st_mtime)

        elif doc_type == DocumentType.JOURNAL:
            # Journals: identifier is window label, sanitized to filename
            # Window labels like "2025-01-11 10:00 to 12:00" → "journal_2025-01-11_10-00_to_12-00.md"
            safe_label = identifier.replace(" ", "_").replace(":", "-")
            path = self.journal_dir / f"journal_{safe_label}.md"

        elif doc_type == DocumentType.ENRICHMENT_URL:
            # URL enrichments: identifier is likely a slug or hash
            path = self.urls_dir / f"{identifier}.md"

        elif doc_type == DocumentType.ENRICHMENT_MEDIA:
            # Media enrichments: stored next to media with .md extension
            path = self.media_dir / f"{identifier}.md"

        elif doc_type == DocumentType.MEDIA:
            # Media files: direct filename lookup
            path = self.media_dir / identifier

        if path is None or not path.exists():
            logger.debug("Document not found: %s/%s", doc_type.value, identifier)
            return None

        # Read file content
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            logger.exception("Failed to read document at %s", path)
            return None

        # Parse frontmatter to extract metadata (if present)
        metadata: dict = {}
        actual_content = content

        if content.startswith("---\n"):
            # Has YAML frontmatter
            try:
                import yaml

                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    frontmatter_yaml = parts[1]
                    actual_content = parts[2].strip()
                    metadata = yaml.safe_load(frontmatter_yaml) or {}
            except (ImportError, yaml.YAMLError) as e:
                logger.warning("Failed to parse frontmatter for %s: %s", path, e)

        # Reconstruct Document (note: document_id will be recalculated from content)
        from egregora.core.document import Document

        return Document(content=actual_content, type=doc_type, metadata=metadata)

    def list_documents(self, doc_type: DocumentType | None = None) -> list[Document]:
        """List all documents, optionally filtered by type.

        Phase 6: Enables listing documents without direct filesystem access.

        Args:
            doc_type: Optional document type filter

        Returns:
            List of documents

        """
        from egregora.core.document import Document

        documents: list[Document] = []

        # Helper to read all files from a directory with a specific type
        def read_dir(directory: Path, dtype: DocumentType, pattern: str = "*.md") -> None:
            if not directory.exists():
                return
            for file_path in directory.glob(pattern):
                # Extract identifier from path
                identifier = file_path.stem
                if dtype == DocumentType.POST:
                    # Extract slug from filename like "2025-01-11-my-post.md"
                    parts = identifier.split("-", 3)
                    if len(parts) >= 4:
                        identifier = parts[3]  # slug
                    else:
                        identifier = identifier
                doc = self.read_document(dtype, identifier)
                if doc:
                    documents.append(doc)

        # Read based on filter
        if doc_type is None:
            # Read all types
            read_dir(self.profiles_dir, DocumentType.PROFILE)
            read_dir(self.posts_dir, DocumentType.POST)
            read_dir(self.journal_dir, DocumentType.JOURNAL)
            read_dir(self.urls_dir, DocumentType.ENRICHMENT_URL)
            # Note: MEDIA and ENRICHMENT_MEDIA not included in default list
        elif doc_type == DocumentType.PROFILE:
            read_dir(self.profiles_dir, DocumentType.PROFILE)
        elif doc_type == DocumentType.POST:
            read_dir(self.posts_dir, DocumentType.POST)
        elif doc_type == DocumentType.JOURNAL:
            read_dir(self.journal_dir, DocumentType.JOURNAL)
        elif doc_type == DocumentType.ENRICHMENT_URL:
            read_dir(self.urls_dir, DocumentType.ENRICHMENT_URL)
        elif doc_type == DocumentType.ENRICHMENT_MEDIA:
            read_dir(self.media_dir, DocumentType.ENRICHMENT_MEDIA, "*.md")
        elif doc_type == DocumentType.MEDIA:
            # Read all non-markdown files in media_dir
            if self.media_dir.exists():
                for file_path in self.media_dir.iterdir():
                    if file_path.is_file() and file_path.suffix != ".md":
                        try:
                            content = file_path.read_bytes()
                            documents.append(
                                Document(
                                    content=content.decode("utf-8", errors="ignore"), type=DocumentType.MEDIA
                                )
                            )
                        except (OSError, UnicodeDecodeError) as e:
                            logger.warning("Failed to read media file %s: %s", file_path, e)

        return documents

    def _url_to_path(self, url: str, document: Document) -> Path:
        """Convert URL to filesystem path.

        Args:
            url: Canonical URL (e.g., "https://example.com/posts/2025-01-11-my-post/")
            document: Document being served (for type-specific logic)

        Returns:
            Filesystem path relative to site_root

        """
        # Strip base_url to get URL path
        base = self._ctx.base_url.rstrip("/")
        if url.startswith(base):
            url_path = url[len(base) :]
        else:
            url_path = url

        # Remove leading slash and trailing slash
        url_path = url_path.strip("/")

        # Convert URL segments to path
        if document.type == DocumentType.POST:
            # /posts/{date}-{slug}/ → posts/{date}-{slug}.md
            return self.site_root / f"{url_path}.md"
        if document.type == DocumentType.PROFILE:
            # /profiles/{uuid}/ → profiles/{uuid}.md
            return self.site_root / f"{url_path}.md"
        if document.type == DocumentType.JOURNAL:
            # /posts/journal/journal_{label}/ → posts/journal/journal_{label}.md
            return self.site_root / f"{url_path}.md"
        if document.type == DocumentType.ENRICHMENT_URL:
            # /docs/media/urls/{doc_id}/ → docs/media/urls/{doc_id}.md
            return self.site_root / f"{url_path}.md"
        if document.type in (DocumentType.ENRICHMENT_MEDIA, DocumentType.MEDIA):
            # /docs/media/{filename} → docs/media/{filename}
            return self.site_root / url_path
        # Fallback
        return self.site_root / f"{url_path}.md"

    def _write_document(self, document: Document, path: Path) -> None:
        """Write document to filesystem with appropriate format.

        Args:
            document: Document to write
            path: Filesystem path to write to

        """
        import yaml

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Handle different document types
        if document.type in (DocumentType.POST, DocumentType.JOURNAL):
            # Write with YAML frontmatter
            yaml_front = yaml.dump(
                document.metadata, default_flow_style=False, allow_unicode=True, sort_keys=False
            )
            full_content = f"---\n{yaml_front}---\n\n{document.content}"
            path.write_text(full_content, encoding="utf-8")

        elif document.type == DocumentType.PROFILE:
            # Lazy import to avoid circular dependency
            from egregora.agents.shared.profiler import write_profile as write_profile_content

            # Use write_profile_content (handles frontmatter + .authors.yml)
            author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
            if not author_uuid:
                msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
                raise ValueError(msg)
            write_profile_content(author_uuid, document.content, self.profiles_dir)

        elif document.type == DocumentType.ENRICHMENT_URL:
            # URL enrichment with optional frontmatter
            if document.parent_id or document.metadata:
                metadata = document.metadata.copy()
                if document.parent_id:
                    metadata["parent_id"] = document.parent_id

                yaml_front = yaml.dump(
                    metadata, default_flow_style=False, allow_unicode=True, sort_keys=False
                )
                full_content = f"---\n{yaml_front}---\n\n{document.content}"
                path.write_text(full_content, encoding="utf-8")
            else:
                path.write_text(document.content, encoding="utf-8")

        elif document.type == DocumentType.ENRICHMENT_MEDIA:
            # Media enrichment - plain markdown
            path.write_text(document.content, encoding="utf-8")

        elif document.type == DocumentType.MEDIA:
            # Media file - binary or text content
            if isinstance(document.content, bytes):
                path.write_bytes(document.content)
            else:
                path.write_text(document.content, encoding="utf-8")

        # Default: write content as-is
        elif isinstance(document.content, bytes):
            path.write_bytes(document.content)
        else:
            path.write_text(document.content, encoding="utf-8")

    def _get_document_id_at_path(self, path: Path) -> str | None:
        """Get document_id of document at path (for idempotency check).

        Args:
            path: Filesystem path to check

        Returns:
            Document ID if readable, None otherwise

        """
        if not path.exists():
            return None

        # TODO: Parse frontmatter to extract document_id for proper idempotency
        # For now, assume different document (conservative approach - will cause collision handling)
        return None

    def _resolve_collision(self, path: Path, document_id: str) -> Path:
        """Resolve path collision by adding numeric suffix.

        Args:
            path: Original path that collided
            document_id: Document ID being served

        Returns:
            New path with numeric suffix

        """
        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 1
        while True:
            new_path = parent / f"{stem}-{counter}{suffix}"
            if not new_path.exists():
                return new_path

            # Check if existing file has same document_id
            existing_doc_id = self._get_document_id_at_path(new_path)
            if existing_doc_id == document_id:
                return new_path

            counter += 1
            if counter > 1000:  # Safety limit
                msg = f"Failed to resolve collision for {path} after 1000 attempts"
                raise RuntimeError(msg)
