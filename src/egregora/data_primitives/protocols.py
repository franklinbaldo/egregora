"""Protocols that define storage and URL contracts for output adapters.

ISP-COMPLIANT PROTOCOLS (2025-11-22):
- OutputSink: Runtime data operations (persist, read, list)
- SiteScaffolder: Project lifecycle operations (init, scaffold)

LEGACY:
- OutputAdapter: Monolithic protocol (deprecated, use OutputSink)
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

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


# ============================================================================
# ISP-COMPLIANT PROTOCOLS (Modern)
# ============================================================================


class OutputSink(Protocol):
    """Runtime data plane for document persistence and retrieval.

    This protocol defines the contract for moving documents in/out of storage
    during pipeline execution. Compatible with filesystems, databases, object
    storage (S3), headless CMS (Strapi, Contentful), and other backends.

    **Separation of Concerns**: This protocol is ONLY for data operations.
    For project initialization/scaffolding, see SiteScaffolder protocol.

    **Used by**: Pipeline orchestration, agents, self-reflection adapter

    **Example implementations**:
    - MkDocsAdapter: Persists to local filesystem (posts/, profiles/)
    - PostgresAdapter: Persists to database tables
    - S3Adapter: Persists to object storage
    - NotionAdapter: Persists to Notion blocks via API
    """

    @property
    def url_convention(self) -> UrlConvention:
        """Return the URL convention adopted by this sink."""

    def persist(self, document: Document) -> None:
        """Persist ``document`` so that it becomes available at its canonical URL.

        This method is idempotent: writing the same document twice with the
        same identifier should UPDATE the existing document, not create a duplicate.

        Args:
            document: Document to persist

        Notes:
            - Posts (slug+date): Overwrites existing file for same slug/date
            - Profiles (UUID): Overwrites existing profile for same UUID
            - Enrichments (hash): Detects collisions, resolves with suffix

        """

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a single document by its ``doc_type`` primary identifier.

        Args:
            doc_type: Type of document to retrieve
            identifier: Primary identifier (e.g., UUID for profiles, slug for posts)

        Returns:
            Document if found, None otherwise

        """

    def list_documents(self, doc_type: DocumentType | None = None) -> Table:
        """Return all known documents as an Ibis table, optionally filtered by ``doc_type``.

        Used by RAG indexing for incremental updates.

        Args:
            doc_type: Optional filter by document type

        Returns:
            Ibis Table with columns:
                - storage_identifier: string (format-specific identifier)
                - mtime_ns: int64 (modification time in nanoseconds)

        """

    def documents(self) -> Iterator[Document]:
        """Return all managed documents as Document objects (lazy iterator).

        Used by self-reflection adapter to re-ingest published posts.
        Returns lazy iterator for memory efficiency.

        Returns:
            Iterator of Document objects (all types)

        Notes:
            - Changed to Iterator in PR #855 (memory optimization)
            - Materialize with list() if you need len() or random access

        """

    def resolve_document_path(self, identifier: str) -> Path:
        """Resolve storage identifier (from ``list_documents``) to actual filesystem path.

        Enables format-agnostic document reingestion.

        Args:
            identifier: Storage identifier from list_documents()

        Returns:
            Absolute filesystem path to the document

        Examples:
            >>> # MkDocs: identifier is relative path from site_root
            >>> sink.resolve_document_path("posts/2025-01-10-post.md")
            Path("/path/to/site/posts/2025-01-10-post.md")

            >>> # Database: identifier is record ID, exports to temp file
            >>> sink.resolve_document_path("post:123")
            Path("/tmp/egregora-cache/post-123.md")

        """


class SiteScaffolder(Protocol):
    """Project lifecycle management for local site initialization.

    This protocol defines the contract for creating and managing site directory
    structures, config files, and project templates. Only implemented by adapters
    that manage local filesystem environments (MkDocs, Hugo, Jekyll, etc.).

    **Separation of Concerns**: This protocol is ONLY for setup/initialization.
    For runtime data operations, see OutputSink protocol.

    **Used by**: CLI (egregora init), initialization utilities

    **Example implementations**:
    - MkDocsAdapter: Creates mkdocs.yml, posts/, profiles/, .egregora/
    - HugoAdapter: Creates config.toml, content/, static/, themes/
    - JekyllAdapter: Creates _config.yml, _posts/, _layouts/

    **Not implemented by**:
    - PostgresAdapter: No filesystem scaffolding needed
    - S3Adapter: No local directory structure
    - NotionAdapter: No filesystem scaffolding (API-based)
    """

    def scaffold_site(self, site_root: Path, site_name: str, **kwargs: object) -> tuple[Path, bool]:
        """Initialize directory structure, config files, and assets.

        Creates all necessary files and directories for a new site. Idempotent:
        returns (config_path, False) if site already exists.

        Args:
            site_root: Root directory for the site
            site_name: Display name for the site
            **kwargs: Format-specific options

        Returns:
            tuple of (config_file_path, was_created)
                - config_file_path: Path to main config file (mkdocs.yml, config.toml, etc.)
                - was_created: True if new site was created, False if already existed

        Raises:
            RuntimeError: If scaffolding fails

        Examples:
            >>> scaffolder = MkDocsAdapter()
            >>> config_path, created = scaffolder.scaffold_site(
            ...     Path("./my-blog"), "My Blog"
            ... )
            >>> # Creates: mkdocs.yml, posts/, profiles/, media/, .egregora/

        """

    def supports_site(self, site_root: Path) -> bool:
        """Check if this scaffolder can handle the given site.

        Used for auto-detection of site format.

        Args:
            site_root: Path to check

        Returns:
            True if this format can handle the site, False otherwise

        Examples:
            >>> MkDocsAdapter().supports_site(Path("./my-blog"))
            True  # if mkdocs.yml exists

        """

    def resolve_paths(self, site_root: Path) -> dict[str, Any]:
        """Resolve all paths for an existing site.

        Returns site configuration with resolved directory paths.

        Args:
            site_root: Root directory of the site

        Returns:
            Dictionary with site configuration (site_root, docs_dir, posts_dir, etc.)

        Raises:
            ValueError: If site_root is not a valid site
            FileNotFoundError: If required directories don't exist

        """


# ============================================================================
# LEGACY PROTOCOL (Backward Compatibility)
# ============================================================================


class OutputAdapter(Protocol):
    """Unified protocol for persisting and retrieving documents.

    DEPRECATED: This monolithic protocol violates the Interface Segregation
    Principle by combining runtime data operations with project lifecycle
    management. New code should use:
        - OutputSink: For runtime data operations
        - SiteScaffolder: For project initialization

    This protocol is maintained for backward compatibility only.
    """

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
