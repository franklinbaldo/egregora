"""Content-addressed document abstraction and storage protocols.

Documents represent all content produced by the Egregora pipeline (posts, profiles,
journals, enrichments). They use content-addressed IDs (UUID v5 of content hash)
for deterministic identity and deduplication.

This module also defines the protocols for output sinks and URL conventions,
unifying the data structures with their persistence contracts.

Core has no opinions about storage - output formats decide paths and filenames.
"""

from __future__ import annotations

import builtins
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID, uuid5

from egregora.data_primitives.text import slugify as _slugify

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


# Well-known namespace for Egregora documents
# Based on DNS namespace but specific to Egregora
NAMESPACE_DOCUMENT = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass(frozen=True, slots=True)
class Author:
    """Represents a content author."""

    id: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class Category:
    """Represents a content category or tag."""

    term: str


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
    ENRICHMENT_MEDIA = "enrichment_media"  # Media file descriptions (generic fallback)
    ENRICHMENT_IMAGE = "enrichment_image"  # Image descriptions
    ENRICHMENT_VIDEO = "enrichment_video"  # Video descriptions
    ENRICHMENT_AUDIO = "enrichment_audio"  # Audio descriptions
    MEDIA = "media"  # Downloaded media files (images, videos, audio)
    ANNOTATION = "annotation"  # Conversation annotations captured during writing


@dataclass(frozen=True, slots=True)
class Document:
    r"""Content-addressed document produced by the pipeline.

    Core abstraction for all generated content.

    REFACTOR (2025-11-28): Adopts "Semantic Identity".
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

    # Internal system metadata (not serialized to public outputs if possible)
    internal_metadata: dict[str, Any] = field(default_factory=dict)

    # Pure: Explicit ID (Semantic Identity)
    id: str | None = field(default=None)

    # Parent relationship (for enrichments)
    parent_id: str | None = None
    parent: Document | None = field(default=None, repr=False, compare=False)

    # Provenance
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_window: str | None = None

    # Hints for output formats (optional, not authoritative)
    suggested_path: str | None = None

    def _clean_slug(self, value: Any) -> str | None:
        """Clean and validate a slug value.

        Args:
            value: Raw slug value from metadata (could be any type)

        Returns:
            Cleaned slug string if valid, None otherwise

        """
        if isinstance(value, str) and (stripped := value.strip()):
            return _slugify(stripped, max_len=60)
        return None

    @property
    def document_id(self) -> str:
        """Return the document's stable identifier.

        Strategy (Pure):
        1. Explicit ID (self.id)
        2. Semantic Slug (for POST/MEDIA if present)
        3. Content-based UUIDv5 (Fallback)
        """
        # 1. Explicit ID
        if self.id:
            return self.id

        # 2. Semantic Identity (Slug)
        # Only for Posts and Media, as per Pure spec
        if (
            self.type in (DocumentType.POST, DocumentType.MEDIA)
            # Do NOT call self.slug property here to avoid recursion fallback loop
            and (cleaned_slug := self._clean_slug(self.metadata.get("slug")))
        ):
            return cleaned_slug

        # 3. Fallback: Content-addressed UUIDv5
        payload = self.content if isinstance(self.content, bytes) else self.content.encode("utf-8")
        content_hash = hashlib.sha256(payload).hexdigest()
        return str(uuid5(NAMESPACE_DOCUMENT, content_hash))

    @property
    def slug(self) -> str:
        """Return a human-friendly identifier when available."""
        if cleaned_slug := self._clean_slug(self.metadata.get("slug")):
            return cleaned_slug

        # Fallback: if we have an explicit ID, use it (it might be a slug)
        if self.id:
            return self.id

        # Fallback: use the first 8 characters of the full document_id
        return self.document_id[:8]

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


@dataclass(frozen=True, slots=True)
class UrlContext:
    """Context information required when generating canonical URLs."""

    base_url: str = ""
    site_prefix: str = ""
    base_path: Path | None = None
    locale: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Lightweight description of a document available in an output sink.

    Used for efficient document enumeration without loading full content.
    Returned by OutputSink.list() for memory-efficient iteration.
    """

    identifier: str
    doc_type: DocumentType | None
    metadata: dict[str, object]


class UrlConvention(Protocol):
    """Contract for deterministic URL generation strategies.

    CRITICAL: This is a PURELY LOGICAL protocol. Implementations must:
    - Use ONLY string operations (no Path, no filesystem concepts)
    - Return URLs as strings ('/posts/foo/' or 'https://example.com/posts/foo/')
    - Have NO knowledge of filesystem layout (docs_dir, file extensions, etc.)

    Filesystem path resolution is the responsibility of OutputAdapter implementations,
    not UrlConvention. This separation enables:
    - Pure URL conventions that work with any backend (filesystem, S3, database)
    - Clean testing of URL logic without filesystem dependencies
    - Flexibility to change file layouts without changing URL structure

    Example of correct implementation:
        class MyConvention(UrlConvention):
            def canonical_url(self, doc: Document, ctx: UrlContext) -> str:
                # ✅ String manipulation only
                slug = doc.metadata.get("slug", doc.document_id[:8])
                return f"{ctx.base_url}/posts/{slug}/"

    Example of INCORRECT implementation:
        class BadConvention(UrlConvention):
            def canonical_url(self, doc: Document, ctx: UrlContext) -> str:
                # ❌ WRONG: Using Path operations
                from pathlib import Path
                path = Path(doc.suggested_path).with_suffix("").as_posix()
                return f"{ctx.base_url}/{path}/"
    """

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


@runtime_checkable
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

    **Runtime Checkable**: Use isinstance(obj, OutputSink) for type checking
    """

    @property
    def url_convention(self) -> UrlConvention:
        """Return the URL convention adopted by this sink."""

    @property
    def url_context(self) -> UrlContext:
        """Return the URL context for canonical URL generation."""

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

    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a single document by its ``doc_type`` primary identifier.

        Args:
            doc_type: Type of document to retrieve
            identifier: Primary identifier (e.g., UUID for profiles, slug for posts)

        Returns:
            Document if found, None otherwise

        """

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """Iterate through available documents, optionally filtering by ``doc_type``.

        Returns lightweight DocumentMetadata objects for memory-efficient enumeration.
        For full document content, use documents() or get().

        Args:
            doc_type: Optional filter by document type

        Returns:
            Iterator of DocumentMetadata (identifier, doc_type, metadata)

        Examples:
            >>> for meta in sink.list(DocumentType.POST):
            ...     print(f"Post: {meta.identifier}, Modified: {meta.metadata['mtime_ns']}")

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

    def get_format_instructions(self) -> str:
        """Get instructions on how to format content for this sink."""
        ...

    def finalize_window(
        self,
        window_label: str,
        _posts_created: builtins.list[str],
        profiles_updated: builtins.list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Hook called after processing a window."""
        ...


@runtime_checkable
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
    - S3Adapter: No filesystem scaffolding (API-based)
    - NotionAdapter: No filesystem scaffolding (API-based)

    **Runtime Checkable**: Use isinstance(obj, SiteScaffolder) for type checking
    """

    def scaffold_site(self, site_root: Path, site_name: str, **kwargs: object) -> tuple[Path, bool]:
        """Initialize directory structure, config files, and assets.

        Full-featured method with explicit return values. Creates all necessary
        files and directories for a new site. Idempotent: returns (config_path, False)
        if site already exists.

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

        Examples:
            >>> paths = scaffolder.resolve_paths(Path("./my-blog"))
            >>> paths["posts_dir"]
            Path("/abs/path/to/my-blog/docs/posts")

        """
