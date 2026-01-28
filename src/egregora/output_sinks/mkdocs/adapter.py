"""MkDocs output adapters and filesystem helpers.

This module consolidates all MkDocs-specific logic that used to live across
``mkdocs.py``, ``mkdocs_output_adapter.py``, ``mkdocs_site.py`` and
``mkdocs_storage.py``.  It exposes the ``MkDocsOutputAdapter``
alongside shared helpers for resolving site
configuration and working with MkDocs' filesystem layout.

MODERN (2025-11-18): Imports site path resolution from
``egregora.output_adapters.mkdocs.paths`` to eliminate duplication.
"""

from __future__ import annotations

import logging
import shutil
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.data_primitives.document import (
    Document,
    DocumentMetadata,
    DocumentType,
    UrlContext,
    UrlConvention,
)
from egregora.data_primitives.text import slugify
from egregora.database.protocols import StorageProtocol
from egregora.knowledge.profiles import generate_fallback_avatar_url
from egregora.output_sinks.base import BaseOutputSink, SiteConfiguration
from egregora.output_sinks.conventions import RouteConfig, StandardUrlConvention
from egregora.output_sinks.exceptions import (
    AdapterNotInitializedError,
    CollisionResolutionError,
    ConfigLoadError,
    DirectoryCreationError,
    DocumentNotFoundError,
    DocumentParsingError,
    FilesystemOperationError,
    FileWriteError,
    ProfileMetadataError,
    UnsupportedDocumentTypeError,
)
from egregora.output_sinks.mkdocs.markdown import write_markdown_post
from egregora.output_sinks.mkdocs.paths import MkDocsPaths
from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder, safe_yaml_load

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


class MkDocsAdapter(BaseOutputSink):
    """Unified MkDocs output adapter.

    **ISP-COMPLIANT** (2025-11-22): This adapter implements both:
    - OutputSink: Runtime data operations (persist, read, list documents)
    - SiteScaffolder: Project lifecycle operations (scaffold_site, supports_site, resolve_paths)

    This dual implementation makes MkDocsAdapter suitable for:
    1. Pipeline execution (via OutputSink interface)
    2. Site initialization (via SiteScaffolder interface)

    Site scaffolding is delegated to :class:`MkDocsSiteScaffolder` to keep
    runtime persistence concerns separate from one-time setup.

    For adapters that only need data persistence (e.g., PostgresAdapter, S3Adapter),
    implement only OutputSink. For pure initialization tools, implement only SiteScaffolder.
    """

    def __init__(self, storage: StorageProtocol | None = None) -> None:
        """Initializes the adapter.

        Args:
            storage: Storage backend for database-backed document reading

        """
        self._scaffolder = MkDocsSiteScaffolder()
        self._initialized = False
        self.site_root = None
        self._url_convention = StandardUrlConvention()
        self._index: dict[str, Path] = {}
        self._ctx: UrlContext | None = None
        self._template_env: Environment | None = None
        self._storage: StorageProtocol | None = storage

    def initialize(
        self,
        site_root: Path,
        url_context: UrlContext | None = None,
        storage: StorageProtocol | None = None,
        **kwargs: Any,
    ) -> None:
        """Initializes the adapter with all necessary paths and dependencies.

        Args:
            site_root: Root directory of the site
            url_context: URL context for canonical URL generation
            storage: Storage backend for database-backed document reading

        """
        try:
            site_paths = MkDocsPaths(site_root)
            self.site_root = site_paths.site_root
            self._site_root = self.site_root
            self.docs_dir = site_paths.docs_dir
            # `site_prefix` is a URL hosting prefix (e.g. '/egregora'), not a filesystem directory like `docs/`.
            # Default to empty unless explicitly provided by the caller.
            self._ctx = url_context or UrlContext(base_url="", site_prefix="", base_path=self.site_root)
            self.posts_dir = site_paths.posts_dir
            self.profiles_dir = site_paths.profiles_dir
            # Journal entries are stored in the configured journal directory (defaults to posts/journal)
            self.journal_dir = site_paths.journal_dir
            self.media_dir = site_paths.media_dir
            self.urls_dir = self.media_dir / "urls"

            # Store storage if provided (overrides __init__ value)
            if storage is not None:
                self._storage = storage

            self.posts_dir.mkdir(parents=True, exist_ok=True)
            self.profiles_dir.mkdir(parents=True, exist_ok=True)
            self.media_dir.mkdir(parents=True, exist_ok=True)
            self.urls_dir.mkdir(parents=True, exist_ok=True)
            self.journal_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Catch any filesystem error during initialization (including from MkDocsPaths)
            raise DirectoryCreationError(str(site_root), e) from e

        # Configure URL convention to match filesystem layout
        # This ensures that generated URLs align with where files are actually stored
        routes = RouteConfig(
            posts_prefix=self.posts_dir.relative_to(self.docs_dir).as_posix(),
            profiles_prefix=self.profiles_dir.relative_to(self.docs_dir).as_posix(),
            media_prefix=self.media_dir.relative_to(self.docs_dir).as_posix(),
            journal_prefix=self.journal_dir.relative_to(self.docs_dir).as_posix(),
        )
        self._url_convention = StandardUrlConvention(routes)

        # Internal dispatch for writers and path resolvers
        self._writers = {
            DocumentType.PROFILE: self._write_profile_doc,
            DocumentType.MEDIA: self._write_media_doc,
            DocumentType.JOURNAL: self._write_journal_doc,
            DocumentType.ENRICHMENT_URL: self._write_enrichment_doc,
            DocumentType.ENRICHMENT_MEDIA: self._write_enrichment_doc,
            DocumentType.ENRICHMENT_IMAGE: self._write_enrichment_doc,
            DocumentType.ENRICHMENT_VIDEO: self._write_enrichment_doc,
            DocumentType.ENRICHMENT_AUDIO: self._write_enrichment_doc,
            DocumentType.ANNOTATION: self._write_annotation_doc,
        }

        # Initialize Jinja2 environment for template-based rendering
        templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
        self._template_env = Environment(
            loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape()
        )

        self._initialized = True

    def scaffold_site(self, site_root: Path, site_name: str, **kwargs: object) -> tuple[Path, bool]:
        """Create or update an MkDocs site using the dedicated scaffolder."""
        result = self._scaffolder.scaffold_site(site_root, site_name, **kwargs)
        # Ensure .authors.yml exists after scaffolding
        self._scaffold_authors_file(site_root)
        return result

    def _scaffold_authors_file(self, site_root: Path) -> None:
        """Create initial .authors.yml file if it doesn't exist."""
        # Check both site root and docs dir (MkDocs standard vs potential override)
        # The blog plugin usually looks in docs_dir if configured, or site_root.
        # We put it in docs_dir as per MkDocs Material recommendation for blog plugin
        # but also verify adapter logic looks there.
        # MkDocsAdapter._append_author_cards looks in site_root/docs/.authors.yml and site_root/.authors.yml.

        # We use the resolved docs_dir if possible, otherwise guess "docs"
        docs_dir = site_root / "docs"
        try:
            if not docs_dir.exists():
                docs_dir.mkdir(parents=True, exist_ok=True)

            authors_file = docs_dir / ".authors.yml"

            if not authors_file.exists():
                # Create empty but valid YAML
                authors_file.write_text("# Authors metadata\n", encoding="utf-8")
                logger.info("Created initial authors file at %s", authors_file)
        except OSError as e:
            raise FileWriteError(str(docs_dir / ".authors.yml"), e) from e

    @property
    def format_type(self) -> str:
        """Return 'mkdocs' as the format type identifier."""
        return "mkdocs"

    @property
    def url_convention(self) -> UrlConvention:
        return self._url_convention

    @property
    def url_context(self) -> UrlContext:
        return self._ctx

    def _get_author_dir(self, author_uuid: str) -> Path:
        """Get or create author's folder in posts/authors/{uuid}/.

        Args:
            author_uuid: Full UUID of the author

        Returns:
            Path to author's folder (created if doesn't exist)

        """
        # Use full UUID for consistency and unambiguous identification
        author_dir = self.posts_dir / "authors" / author_uuid
        author_dir.mkdir(parents=True, exist_ok=True)
        return author_dir

    def persist(self, document: Document) -> None:
        doc_id = document.document_id
        url = self._url_convention.canonical_url(document, self._ctx)
        path = self._url_to_path(url, document)

        if doc_id in self._index:
            old_path = self._index[doc_id]
            if old_path != path and old_path.exists():
                logger.info("Moving document %s: %s → %s", doc_id[:8], old_path, path)
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if path.exists():
                        old_path.unlink()
                    else:
                        old_path.rename(path)
                except OSError as e:
                    raise FilesystemOperationError(str(old_path), e, f"Failed to move document: {e}") from e

        if path.exists() and document.type == DocumentType.ENRICHMENT_URL:
            existing_doc_id = self._get_document_id_at_path(path)
            if existing_doc_id and existing_doc_id != doc_id:
                path = self._resolve_collision(path, doc_id)
                logger.warning("Hash collision for %s, using %s", doc_id[:8], path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise DirectoryCreationError(str(path.parent), e) from e

        if document.type == DocumentType.POST:
            metadata = document.metadata
            # Add related posts based on shared tags
            current_tags = set(metadata.get("tags", []))
            current_slug = metadata.get("slug")
            if current_tags and current_slug:
                all_posts = list(self.documents())
                related_posts_list = []
                for post in all_posts:
                    if post.type != DocumentType.POST:
                        continue
                    post_slug = post.metadata.get("slug")
                    if post_slug == current_slug:
                        continue
                    post_tags = set(post.metadata.get("tags", []))
                    shared_tags = current_tags & post_tags
                    if shared_tags:
                        related_posts_list.append(
                            {
                                "title": post.metadata.get("title"),
                                "url": self.url_convention.canonical_url(post, self._ctx),
                                "reading_time": post.metadata.get("reading_time", 5),
                            }
                        )
                if related_posts_list:
                    metadata["related_posts"] = related_posts_list
            content = document.content
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            write_markdown_post(content, metadata, self.posts_dir)
        else:
            # Dispatch to specific writer if available, else generic
            writer = self._writers.get(document.type, self._write_generic_doc)
            writer(document, path)

        self._index[doc_id] = path
        logger.debug("Served document %s at %s", doc_id, path)

    def _resolve_document_path(self, doc_type: DocumentType, identifier: str) -> Path:
        """Resolve filesystem path for a document based on its type.

        UNIFIED: Posts, profiles, journals, and enrichment URLs all live in posts_dir.
        We distinguish them by filename patterns and category metadata.

        Args:
            doc_type: Type of document
            identifier: Document identifier

        Returns:
            Path to document

        """
        match doc_type:
            case DocumentType.PROFILE:
                # Profiles: "author_uuid/slug" (preferred) or "author_uuid" (latest)
                if "/" in identifier:
                    author_uuid, slug = identifier.split("/", 1)
                    return self.profiles_dir / author_uuid / f"{slug}.md"
                author_dir = self.profiles_dir / identifier
                index_path = author_dir / "index.md"
                if index_path.exists():
                    return index_path

                if not author_dir.exists():
                    raise DocumentNotFoundError(doc_type.value, identifier)

                candidates = [p for p in author_dir.glob("*.md") if p.name != "index.md"]
                if not candidates:
                    raise DocumentNotFoundError(doc_type.value, identifier)
                return max(candidates, key=lambda p: p.stat().st_mtime_ns)
            case DocumentType.POST:
                # Posts: dated filename (e.g., "2024-01-01-slug.md")
                matches = list(self.posts_dir.glob(f"*-{identifier}.md"))
                if not matches:
                    raise DocumentNotFoundError(doc_type.value, identifier)
                return max(matches, key=lambda p: p.stat().st_mtime)
            case DocumentType.JOURNAL:
                # Journals: simple filename with slug in journal_dir
                return self.journal_dir / f"{identifier.replace('/', '-')}.md"
            case DocumentType.ENRICHMENT_URL:
                # Enrichment URLs: inside media_dir/urls (ADR-0004)
                return self.media_dir / "urls" / f"{identifier}.md"
            case DocumentType.ENRICHMENT_MEDIA:
                # Enrichment media: stays in media_dir (fallback)
                return self.media_dir / f"{identifier}.md"
            case DocumentType.ENRICHMENT_IMAGE:
                # Image descriptions: media_dir/images/
                return self.media_dir / "images" / f"{identifier}.md"
            case DocumentType.ENRICHMENT_VIDEO:
                # Video descriptions: media_dir/videos/
                return self.media_dir / "videos" / f"{identifier}.md"
            case DocumentType.ENRICHMENT_AUDIO:
                # Audio descriptions: media_dir/audio/
                return self.media_dir / "audio" / f"{identifier}.md"
            case DocumentType.MEDIA:
                # Media files: stay in media_dir
                return self.media_dir / identifier
            case _:
                raise UnsupportedDocumentTypeError(str(doc_type))

    def get(self, doc_type: DocumentType, identifier: str) -> Document:
        """Retrieve a document from the database (canonical source).

        This method reads from the database instead of files, making the database
        the single source of truth for all document content.

        Args:
            doc_type: Type of document to retrieve
            identifier: Document identifier (UUID for profiles, slug for posts, etc.)

        Returns:
            Document object

        Raises:
            DocumentNotFoundError: If document not found in database
            DocumentParsingError: If document parsing fails

        """
        # Use database as canonical source if available
        if self._storage is not None:
            from egregora.database.profile_cache import get_profile_from_db

            if doc_type == DocumentType.PROFILE:
                content = get_profile_from_db(self._storage, identifier)
                if not content:
                    raise DocumentNotFoundError(doc_type.value, identifier)

                # Parse frontmatter from content
                post = frontmatter.loads(content)
                return Document(content=post.content, type=doc_type, metadata=post.metadata)

            if doc_type == DocumentType.POST:
                # Query posts table
                table = self._storage.read_table("posts")
                result = table.filter(table.slug == identifier).execute()

                if len(result) == 0:
                    raise DocumentNotFoundError(doc_type.value, identifier)

                row = result.iloc[0]
                # Parse frontmatter from content
                post = frontmatter.loads(row["content"])
                return Document(content=post.content, type=doc_type, metadata=post.metadata)

        # No fallback to file-based reading - database is the single source of truth
        raise DocumentNotFoundError(doc_type.value, identifier)

    def validate_structure(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file.

        Implements SiteScaffolder.validate_structure.
        """
        return self.supports_site(site_root)

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file."""
        return self._scaffolder.supports_site(site_root)

    # SiteScaffolder protocol -------------------------------------------------

    def scaffold(self, path: Path, config: dict) -> None:
        """Compatibility entry point for the scaffolder protocol."""
        self._scaffolder.scaffold(path, config)

    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        """Resolve all paths for an existing MkDocs site."""
        return self._scaffolder.resolve_paths(site_root)

    def load_config(self, site_root: Path) -> dict[str, Any]:
        """Load MkDocs site configuration.

        Args:
            site_root: Root directory of the site

        Returns:
            Dictionary of configuration values from mkdocs.yml

        Raises:
            FileNotFoundError: If mkdocs.yml doesn't exist
            ValueError: If config is invalid

        """
        # Use MkDocsPaths to find mkdocs.yml (checks .egregora/, root)
        site_paths = MkDocsPaths(site_root)
        mkdocs_path = site_paths.mkdocs_path
        if not mkdocs_path:
            raise ConfigLoadError(str(site_root), "No mkdocs.yml found")
        try:
            config = safe_yaml_load(mkdocs_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigLoadError(str(mkdocs_path), str(exc)) from exc
        return config

    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for MkDocs Material theme.

        Reads from configuration if available, otherwise returns standard defaults.

        Returns:
            List of markdown extension identifiers

        """
        # Load from mkdocs.yml if possible
        if self.site_root:
            try:
                config = self.load_config(self.site_root)
                markdown_extensions = config.get("markdown_extensions")
                if markdown_extensions:
                    # Handle both list and dict formats (mkdocs supports both)
                    if isinstance(markdown_extensions, list):
                        return [
                            ext if isinstance(ext, str) else next(iter(ext.keys()))
                            for ext in markdown_extensions
                        ]
                    if isinstance(markdown_extensions, dict):
                        return list(markdown_extensions.keys())
            except (FileNotFoundError, ValueError):
                pass

        # Fallback defaults
        return [
            "tables",
            "fenced_code",
            "footnotes",
            "attr_list",
            "md_in_html",
            "def_list",
            "toc",
            "pymdownx.arithmatex",
            "pymdownx.betterem",
            "pymdownx.caret",
            "pymdownx.mark",
            "pymdownx.tilde",
            "pymdownx.critic",
            "pymdownx.details",
            "pymdownx.emoji",
            "pymdownx.highlight",
            "pymdownx.inlinehilite",
            "pymdownx.keys",
            "pymdownx.magiclink",
            "pymdownx.smartsymbols",
            "pymdownx.superfences",
            "pymdownx.tabbed",
            "pymdownx.tasklist",
            "admonition",
        ]

    def get_format_instructions(self) -> str:
        """Generate MkDocs Material format instructions for the writer agent.

        Returns:
            Markdown-formatted instructions explaining MkDocs Material conventions

        """
        return """## Output Format: MkDocs Material

Your posts will be rendered using MkDocs with the Material for MkDocs theme.

### Front-matter Format

Use **YAML front-matter** between `---` markers at the top of each post:

```yaml
---
title: Your Post Title
date: 2025-01-10
slug: your-post-slug
authors:
  - author-uuid-1
  - author-uuid-2
tags:
  - topic1
  - topic2
summary: A brief 1-2 sentence summary of the post
---
```

**Required fields**: `title`, `date`, `slug`, `authors`, `tags`, `summary`

### File Naming Convention

Posts must be named: `{date}-{slug}.md`

Examples:
- ✅ `2025-01-10-my-post.md`
- ✅ `2025-03-15-technical-discussion.md`
- ❌ `my-post.md` (missing date)
- ❌ `2025-01-10 my post.md` (spaces not allowed)

**Date format**: `YYYY-MM-DD` (ISO 8601)
**Slug format**: lowercase, hyphens only, no spaces or special characters

### Author Attribution

Authors are referenced by **UUID only** (not names) in post front-matter.

Author profiles are defined in `.authors.yml` at the site root:

```yaml
d944f0f7:  # Author UUID (short form)
  name: Casey
  description: "AI researcher and conversation synthesizer"
  avatar: https://example.com/avatar.jpg
```

The MkDocs blog plugin uses `.authors.yml` to generate author cards, archives, and attribution.

### Special Features Available

**Admonitions** (callout boxes):
```markdown
!!! note
    This is a note admonition

!!! warning
    This is a warning

!!! tip
    Pro tip here
```

**Code blocks** with syntax highlighting:
```markdown
\u200b```python
def example():
    return "syntax highlighting works"
\u200b```
```

**Mathematics** (LaTeX):
- Inline: `$E = mc^2$`
- Block: `$$\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$$`

**Task lists**:
```markdown
- [x] Completed task
- [ ] Pending task
```

**Tables**:
```markdown
| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
```

**Tabbed content**:
```markdown
=== "Tab 1"
    Content for tab 1

=== "Tab 2"
    Content for tab 2
```

### Media References

When referencing media (images, videos, audio), use relative paths from the post:

```markdown
![Description](../media/images/uuid.png)
```

Media files are organized in:
- `media/images/` - Images and banners
- `media/videos/` - Video files
- `media/audio/` - Audio files

All media filenames use content-based UUIDs for deterministic naming.

### Best Practices

1. **Use semantic markup**: Headers (`##`, `###`), lists, emphasis
2. **Include summaries**: 1-2 sentence preview for post listings
3. **Tag appropriately**: Use 2-5 relevant tags per post
4. **Reference authors correctly**: Use UUIDs from author profiles
5. **Link media**: Use relative paths to media files
6. **Leverage admonitions**: Highlight important points with callouts
7. **Code examples**: Use fenced code blocks with language specification

### Taxonomy

Tags automatically create taxonomy pages where readers can browse posts by topic.
Use consistent, meaningful tags across posts to build a useful taxonomy.
"""

    def documents(self, doc_type: DocumentType | None = None) -> Iterator[Document]:
        """Return all MkDocs documents as Document instances (database-backed).

        Reads from cached database tables instead of filesystem for performance.
        """
        if not hasattr(self, "_site_root") or self._site_root is None or self._storage is None:
            return

        # Read posts from database
        if doc_type is None or doc_type == DocumentType.POST:
            with suppress(OSError, KeyError, AttributeError):
                posts_table = self._storage.read_table("posts")
                for _, row in posts_table.execute().iterrows():
                    post = frontmatter.loads(row["content"])
                    yield Document(
                        content=post.content,
                        type=DocumentType.POST,
                        metadata=post.metadata,
                    )

        # Read profiles from database
        if doc_type is None or doc_type == DocumentType.PROFILE:
            with suppress(OSError, KeyError, AttributeError):
                profiles_table = self._storage.read_table("profiles")
                for _, row in profiles_table.execute().iterrows():
                    profile = frontmatter.loads(row["content"])
                    yield Document(
                        content=profile.content,
                        type=DocumentType.PROFILE,
                        metadata=profile.metadata,
                    )

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """Iterate through available documents as lightweight DocumentMetadata.

        Returns DocumentMetadata (identifier, doc_type, metadata) for efficient
        enumeration without loading full document content.

        Args:
            doc_type: Optional filter by document type

        Returns:
            Iterator of DocumentMetadata instances

        """
        if not hasattr(self, "_site_root") or self._site_root is None:
            return

        # Scan docs/posts recursively and classify documents by path + frontmatter.
        yield from self._list_from_posts_tree(doc_type)

    def _list_from_posts_tree(self, filter_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        exclude_names = {"index.md", "tags.md"}
        for path in self.posts_dir.rglob("*.md"):
            if not path.is_file() or path.name in exclude_names:
                continue
            if self.media_dir in path.parents and path.name == "index.md":
                continue
            detected_type = self._detect_document_type(path)
            if filter_type is not None and detected_type != filter_type:
                continue
            identifier = str(path.relative_to(self._site_root))
            try:
                mtime_ns = path.stat().st_mtime_ns
            except OSError:
                mtime_ns = 0
            yield DocumentMetadata(
                identifier=identifier,
                doc_type=detected_type,
                metadata={"mtime_ns": mtime_ns, "path": str(path)},
            )

    def _documents_from_dir(
        self,
        directory: Path,
        doc_type: DocumentType,
        *,
        recursive: bool = False,
        exclude_names: set[str] | None = None,
    ) -> list[Document]:
        if not directory or not directory.exists():
            return []

        documents: list[Document] = []
        glob_func = directory.rglob if recursive else directory.glob
        for path in glob_func("*.md"):
            if not path.is_file():
                continue
            if exclude_names and path.name in exclude_names:
                continue
            doc = self._document_from_path(path, doc_type)
            if doc:
                documents.append(doc)
        return documents

    def resolve_document_path(self, identifier: str) -> Path:
        """Resolve MkDocs storage identifier (relative path) to absolute filesystem path.

        Args:
            identifier: Relative path from site_root (e.g., "posts/2025-01-10-my-post.md")

        Returns:
            Path: Absolute filesystem path

        Raises:
            RuntimeError: If output format not initialized

        Example:
            >>> format.resolve_document_path("posts/2025-01-10-my-post.md")
            Path("/path/to/site/posts/2025-01-10-my-post.md")

        """
        if not hasattr(self, "_site_root") or self._site_root is None:
            msg = "MkDocsOutputAdapter not initialized - call initialize() first"
            raise AdapterNotInitializedError(msg)

        # MkDocs identifiers are relative paths from site_root
        return (self._site_root / identifier).resolve()

    # REMOVED: finalize_window() logic for profile regeneration.
    # Rationale: Profile regeneration is now handled by the ProfileWorker and site_generator.py
    # which aggregates stats dynamically. The adapter should focus on persistence (OutputSink)
    # and not orchestration logic.

    def finalize_window(
        self,
        window_label: str,
        _posts_created: list[str],
        profiles_updated: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Post-processing hook called after writer agent completes a window."""
        logger.info(
            "Finalizing window: %s. Site generation is now handled by the orchestration layer.", window_label
        )
        # Site generation logic has been moved to the SiteGenerator class.
        # The orchestrator is responsible for calling it.

    def _detect_document_type(self, path: Path) -> DocumentType:
        """Detect document type from path and (when needed) frontmatter."""
        try:
            relative = path.relative_to(self.posts_dir)
        except ValueError:
            relative = path

        parts = relative.parts
        if parts[:1] == ("profiles",):
            return DocumentType.PROFILE
        if parts[:2] == ("media", "urls"):
            return DocumentType.ENRICHMENT_URL
        if parts[:1] == ("media",):
            return DocumentType.ENRICHMENT_MEDIA
        if parts[:2] == ("annotations",):
            return DocumentType.ANNOTATION

        try:
            post = frontmatter.load(str(path))
            metadata = post.metadata
        except OSError:
            metadata = {}

        categories = (metadata or {}).get("categories", [])
        if not isinstance(categories, list):
            categories = []
        if "Journal" in categories:
            return DocumentType.JOURNAL
        if "Annotations" in categories:
            return DocumentType.ANNOTATION
        return DocumentType.POST

    def _list_from_unified_dir(
        self,
        directory: Path,
        filter_type: DocumentType | None = None,
        *,
        exclude_names: set[str] | None = None,
    ) -> Iterator[DocumentMetadata]:
        """List documents from unified directory, detecting types by category metadata.

        This replaces scanning separate directories for posts, profiles, journals, and enrichments.
        All these document types now live in posts_dir, distinguished by their category metadata.
        """
        if not directory or not directory.exists():
            return

        exclude_set = exclude_names or set()

        for path in directory.glob("*.md"):
            if not path.is_file() or path.name in exclude_set:
                continue

            try:
                # Detect document type by reading category metadata
                detected_type = self._detect_document_type(path)

                # Apply type filter if specified
                if filter_type is not None and detected_type != filter_type:
                    continue

                identifier = str(path.relative_to(self._site_root))
                mtime_ns = path.stat().st_mtime_ns
                yield DocumentMetadata(
                    identifier=identifier,
                    doc_type=detected_type,
                    metadata={"mtime_ns": mtime_ns, "path": str(path)},
                )
            except (OSError, ValueError):
                continue

    def _list_from_dir(
        self,
        directory: Path,
        dtype: DocumentType,
        filter_type: DocumentType | None = None,
        *,
        recursive: bool = False,
        exclude_names: set[str] | None = None,
    ) -> Iterator[DocumentMetadata]:
        """Helper to yield DocumentMetadata from a directory.

        For non-unified directories (media, enrichment media) where all files are the same type.
        """
        if filter_type is not None and filter_type != dtype:
            return

        if not directory or not directory.exists():
            return

        exclude_set = exclude_names or set()
        glob_func = directory.rglob if recursive else directory.glob

        for path in glob_func("*.md"):
            if not path.is_file() or path.name in exclude_set:
                continue

            try:
                identifier = str(path.relative_to(self._site_root))
                mtime_ns = path.stat().st_mtime_ns
                yield DocumentMetadata(
                    identifier=identifier,
                    doc_type=dtype,
                    metadata={"mtime_ns": mtime_ns, "path": str(path)},
                )
            except (OSError, ValueError):
                continue

    def _document_from_path(self, path: Path, doc_type: DocumentType) -> Document:
        try:
            post = frontmatter.load(str(path))
            metadata, body = post.metadata, post.content
        except OSError as e:
            raise DocumentParsingError(str(path), str(e)) from e
        metadata = metadata or {}
        slug_value = metadata.get("slug")
        if isinstance(slug_value, str) and slug_value.strip():
            slug = slugify(slug_value)
        else:
            slug = slugify(path.stem)
        metadata["slug"] = slug
        storage_identifier = str(path.relative_to(self._site_root))
        metadata.setdefault("storage_identifier", storage_identifier)
        metadata.setdefault("source_path", str(path))
        try:
            metadata.setdefault("mtime_ns", path.stat().st_mtime_ns)
        except OSError:
            metadata.setdefault("mtime_ns", 0)
        return Document(content=body.strip(), type=doc_type, metadata=metadata)

    def _url_to_path(self, url: str, document: Document) -> Path:
        base = self._ctx.base_url.rstrip("/")
        url_path = url.removeprefix(base)

        url_path = url_path.strip("/")

        match document.type:
            case DocumentType.POST:
                # ALL regular posts go to top-level posts/
                # (Not to author folders - those are for PROFILE posts ABOUT authors)
                slug = url_path.split("/")[-1]
                return self.posts_dir / f"{slug}.md"

            case DocumentType.PROFILE:
                # PROFILE posts (Egregora writing ABOUT author) go to author's folder
                subject_uuid = document.metadata.get("subject")
                if not subject_uuid:
                    raise ProfileMetadataError(document.document_id, "subject")

                # Successfully routing to author-specific directory
                profile_dir = self.profiles_dir / str(subject_uuid)
                profile_dir.mkdir(parents=True, exist_ok=True)
                slug = url_path.split("/")[-1]
                logger.debug("Routing PROFILE to author directory: %s/%s", subject_uuid, slug)
                return profile_dir / f"{slug}.md"

            case DocumentType.ANNOUNCEMENT:
                # ANNOUNCEMENT posts (user command events) route to author folder if subject exists
                # This creates a unified feed with PROFILE posts
                subject_uuid = document.metadata.get("subject") or document.metadata.get("actor")

                if not subject_uuid:
                    # Fallback: system announcements without subject go to announcements/
                    logger.warning(
                        "ANNOUNCEMENT doc missing 'subject' metadata, falling back to announcements/. "
                        "Document ID: %s, URL: %s",
                        document.document_id,
                        url_path,
                    )
                    slug = url_path.split("/")[-1]
                    announcements_dir = self.posts_dir / "announcements"
                    announcements_dir.mkdir(parents=True, exist_ok=True)
                    return announcements_dir / f"{slug}.md"

                # Route to author's profile feed directory
                profile_dir = self.profiles_dir / str(subject_uuid)
                profile_dir.mkdir(parents=True, exist_ok=True)
                slug = url_path.split("/")[-1]
                logger.debug("Routing ANNOUNCEMENT to author directory: %s/%s", subject_uuid, slug)
                return profile_dir / f"{slug}.md"

            case DocumentType.JOURNAL:
                # Journals now go into posts_dir with journal- prefix
                slug = url_path.split("/")[-1]
                if url_path == "journal":
                    return self.docs_dir / "journal.md"
                return self.posts_dir / f"{slug}.md"
            case DocumentType.ENRICHMENT_URL:
                # url_path might be 'posts/media/urls/slug' -> we want 'slug.md' inside media_dir/urls
                # ADR-0004: URL enrichments go to posts/media/urls/
                slug = url_path.split("/")[-1]
                return self.media_dir / "urls" / f"{slug}.md"
            case DocumentType.ENRICHMENT_MEDIA:
                # url_path is like 'media/images/foo' -> we want 'docs/media/images/foo.md' (fallback)
                rel_path = self._strip_media_prefix(url_path)
                return self.media_dir / f"{rel_path}.md"
            case DocumentType.ENRICHMENT_IMAGE:
                # Images: url_path ends with slug -> media_dir/images/slug.md
                slug = url_path.split("/")[-1]
                return self.media_dir / "images" / f"{slug}.md"
            case DocumentType.ENRICHMENT_VIDEO:
                # Videos: url_path ends with slug -> media_dir/videos/slug.md
                slug = url_path.split("/")[-1]
                return self.media_dir / "videos" / f"{slug}.md"
            case DocumentType.ENRICHMENT_AUDIO:
                # Audio: url_path ends with slug -> media_dir/audio/slug.md
                slug = url_path.split("/")[-1]
                return self.media_dir / "audio" / f"{slug}.md"
            case DocumentType.MEDIA:
                rel_path = self._strip_media_prefix(url_path)
                return self.media_dir / rel_path
            case DocumentType.ANNOTATION:
                # Annotations: inside posts_dir/annotations (by default)
                slug = url_path.split("/")[-1]
                return self.posts_dir / "annotations" / f"{slug}.md"
            case _:
                return self._resolve_generic_path(url_path)

    def _resolve_generic_path(self, url_path: str) -> Path:
        return self.site_root / f"{url_path}.md"

    def _strip_media_prefix(self, url_path: str) -> str:
        """Helper to strip media prefixes from URL path."""
        rel_path = url_path
        media_prefixes: set[str] = set()
        if hasattr(self._url_convention, "routes"):
            prefix = str(getattr(self._url_convention.routes, "media_prefix", "")).strip("/")
            if prefix:
                media_prefixes.add(prefix)
        media_prefixes.update(["media", "posts/media"])

        # Sort by length descending to match longest prefix first
        for prefix in sorted(media_prefixes, key=len, reverse=True):
            if rel_path == prefix:
                rel_path = ""
                break
            if rel_path.startswith(prefix + "/"):
                rel_path = rel_path[len(prefix) + 1 :]
                break
        return rel_path

    def _parse_frontmatter(self, path: Path) -> dict:
        """Extract YAML frontmatter from markdown file.

        Args:
            path: Path to markdown file

        Returns:
            Dictionary of frontmatter metadata (empty if none found)

        """
        try:
            return frontmatter.load(str(path)).metadata
        except OSError:
            return {}

    # Document Writing Strategies ---------------------------------------------

    @staticmethod
    def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        """Remove None values from metadata to prevent YAML nulls."""
        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _ensure_category(metadata: dict[str, Any], category: str) -> dict[str, Any]:
        """Ensure metadata has a valid categories list with the specified category.

        Handles malformed categories (non-list values) by converting to list.
        Avoids duplicate categories.
        """
        categories = metadata.get("categories", [])

        # Handle malformed categories - must be a list
        if not isinstance(categories, list):
            categories = []

        # Add category if not already present
        if category and category not in categories:
            categories.append(category)

        metadata["categories"] = categories
        return metadata

    def _write_journal_doc(self, document: Document, path: Path) -> None:
        metadata = dict(document.metadata or {})
        metadata["type"] = "journal"
        metadata["publish"] = True

        # Add Journal category using helper (handles malformed data)
        metadata = self._ensure_category(metadata, "Journal")
        metadata = self._clean_metadata(metadata)

        yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content = document.content
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        full_content = f"---\n{yaml_front}---\n\n{content}"
        try:
            path.write_text(full_content, encoding="utf-8")
        except OSError as e:
            raise FileWriteError(str(path), e) from e

    def _write_annotation_doc(self, document: Document, path: Path) -> None:
        metadata = self._ensure_hidden(dict(document.metadata or {}))

        # Add type for categorization
        metadata["type"] = "annotation"

        # Add Annotations category using helper (handles malformed data)
        metadata = self._ensure_category(metadata, "Annotations")
        metadata = self._clean_metadata(metadata)

        yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content = document.content
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        full_content = f"---\n{yaml_front}---\n\n{content}"
        try:
            path.write_text(full_content, encoding="utf-8")
        except OSError as e:
            raise FileWriteError(str(path), e) from e

    def _write_profile_doc(self, document: Document, path: Path) -> None:
        # Ensure UUID is in metadata
        author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
        if not author_uuid:
            raise ProfileMetadataError(document.document_id, "'uuid' or 'author_uuid'")

        # Use standard frontmatter writing logic
        metadata = dict(document.metadata or {})

        # Add type for categorization
        metadata["type"] = "profile"

        # Ensure avatar is present (fallback if needed)
        if "avatar" not in metadata:
            metadata["avatar"] = generate_fallback_avatar_url(author_uuid)

        # Add Authors category using helper (handles malformed data)
        metadata = self._ensure_category(metadata, "Authors")

        all_posts = list(self.documents())
        author_posts_docs = [post for post in all_posts if author_uuid in post.metadata.get("authors", [])]
        metadata["posts"] = [
            {
                "title": post.metadata.get("title"),
                "url": self.url_convention.canonical_url(post, self._ctx),
                "date": post.metadata.get("date"),
            }
            for post in author_posts_docs
        ]
        metadata = self._clean_metadata(metadata)

        yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # Avatar is in frontmatter only - not prepended to content
        # This allows the template/theme to handle avatar rendering
        content = document.content
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        full_content = f"---\n{yaml_front}---\n\n{content}"
        try:
            path.write_text(full_content, encoding="utf-8")
        except OSError as e:
            raise FileWriteError(str(path), e) from e

    def _write_enrichment_doc(self, document: Document, path: Path) -> None:
        metadata = self._ensure_hidden(document.metadata.copy())
        metadata.setdefault("slug", document.slug)
        if document.parent_id:
            metadata.setdefault("parent_id", document.parent_id)
        if document.parent and document.parent.metadata.get("slug"):
            metadata.setdefault("parent_slug", document.parent.metadata.get("slug"))

        # Add Enrichment category using helper (handles malformed data)
        metadata = self._ensure_category(metadata, "Enrichment")
        metadata = self._clean_metadata(metadata)

        yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content = document.content
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        full_content = f"---\n{yaml_front}---\n\n{content}"
        try:
            path.write_text(full_content, encoding="utf-8")
        except OSError as e:
            raise FileWriteError(str(path), e) from e

    def _write_media_doc(self, document: Document, path: Path) -> None:
        if document.metadata.get("pii_deleted"):
            logger.info("Skipping persistence of PII-containing media: %s", path.name)
            return

        # Pure Large File Support: If source_path is present, move/copy from there
        # instead of loading content into memory.
        source_path = document.metadata.get("source_path")
        if source_path:
            src = Path(source_path)
            if src.exists():
                logger.debug("Moving media file from %s to %s", src, path)
                # We use move to be efficient (atomic on same filesystem), falling back to copy if needed.
                # Since the source is usually a temp staging file, moving is preferred.
                try:
                    try:
                        shutil.move(src, path)
                    except OSError:
                        # Fallback if cross-device or other issue
                        shutil.copy2(src, path)
                        with suppress(OSError):
                            src.unlink()
                except OSError as e:
                    raise FileWriteError(str(path), e) from e
                return
            logger.warning("Source path %s provided but does not exist, falling back to content", source_path)

        payload = (
            document.content if isinstance(document.content, bytes) else document.content.encode("utf-8")
        )
        try:
            path.write_bytes(payload)
        except OSError as e:
            raise FileWriteError(str(path), e) from e

    def _write_generic_doc(self, document: Document, path: Path) -> None:
        try:
            if isinstance(document.content, bytes):
                path.write_bytes(document.content)
            else:
                path.write_text(document.content, encoding="utf-8")
        except OSError as e:
            raise FileWriteError(str(path), e) from e

    @staticmethod
    def _ensure_hidden(metadata: dict[str, Any]) -> dict[str, Any]:
        """Ensure document is hidden from navigation."""
        hide = metadata.get("hide", [])
        if isinstance(hide, str):
            hide = [hide]
        if "navigation" not in hide:
            hide.append("navigation")
        metadata["hide"] = hide
        metadata["nav_exclude"] = metadata.get("nav_exclude", True)
        return metadata

    def _get_document_id_at_path(self, path: Path) -> str:
        if not path.exists():
            msg = "Unknown"
            raise DocumentNotFoundError(msg, str(path))

        try:
            raw_content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DocumentParsingError(str(path), str(exc)) from exc

        body = raw_content
        metadata: dict[str, Any] = {}

        min_parts_count = 3
        if raw_content.startswith("---\n"):
            try:
                parts = raw_content.split("---\n", 2)
                if len(parts) >= min_parts_count:
                    loaded_metadata = yaml.safe_load(parts[1]) or {}
                    metadata = loaded_metadata if isinstance(loaded_metadata, dict) else {}
                    body = parts[2]
                    body = body.removeprefix("\n")
            except yaml.YAMLError as exc:
                logger.warning("Failed to parse frontmatter for %s: %s", path, exc)
                metadata = {}
                body = raw_content

        metadata_copy = dict(metadata)
        parent_id = metadata_copy.pop("parent_id", None)

        document = Document(
            content=body,
            type=DocumentType.ENRICHMENT_URL,
            metadata=metadata_copy,
            parent_id=parent_id,
        )
        return document.document_id

    def _resolve_collision(self, path: Path, document_id: str) -> Path:
        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 1
        while True:
            new_path = parent / f"{stem}-{counter}{suffix}"
            if not new_path.exists():
                return new_path
            existing_doc_id = self._get_document_id_at_path(new_path)
            if existing_doc_id == document_id:
                return new_path
            counter += 1
            max_attempts = 1000
            if counter > max_attempts:
                raise CollisionResolutionError(str(path), max_attempts)
