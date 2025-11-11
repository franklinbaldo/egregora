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

from egregora.agents.shared.profiler import write_profile as write_profile_content
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

        Args:
            document: Document to serve

        Returns:
            None (void)

        """
        doc_id = document.document_id

        # Check idempotency - if document already served, reuse path
        if doc_id in self._index:
            path = self._index[doc_id]
            logger.debug("Document %s already served at %s (idempotent)", doc_id, path)
        else:
            # Calculate URL using convention
            url = self._url_convention.canonical_url(document, self._ctx)

            # Convert URL to filesystem path
            path = self._url_to_path(url, document)

            # Check if path exists with different document_id (collision)
            if path.exists():
                existing_doc_id = self._get_document_id_at_path(path)
                if existing_doc_id == doc_id:
                    # Same document - idempotent
                    logger.debug("Document %s already at %s (idempotent)", doc_id, path)
                else:
                    # Collision - different document at same URL
                    # Handle by adding numeric suffix
                    path = self._resolve_collision(path, doc_id)

        # Write document at determined path
        self._write_document(document, path)

        # Update index
        self._index[doc_id] = path

        logger.debug("Served document %s at %s", doc_id, path)

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
        if document.type == DocumentType.ENRICHMENT_MEDIA or document.type == DocumentType.MEDIA:
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
