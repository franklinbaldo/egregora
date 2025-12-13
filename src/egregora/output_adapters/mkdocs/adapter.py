"""MkDocs output adapters and filesystem helpers.

This module consolidates all MkDocs-specific logic that used to live across
``mkdocs.py``, ``mkdocs_output_adapter.py``, ``mkdocs_site.py`` and
``mkdocs_storage.py``.  It exposes both the legacy registry-friendly
``MkDocsOutputAdapter`` as well as the modern document-centric
``MkDocsFilesystemAdapter`` alongside shared helpers for resolving site
configuration and working with MkDocs' filesystem layout.

MODERN (2025-11-18): Imports site path resolution from
``egregora.output_adapters.mkdocs.paths`` to eliminate duplication.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape

from egregora.data_primitives import DocumentMetadata
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlContext, UrlConvention
from egregora.knowledge.profiles import generate_fallback_avatar_url
from egregora.output_adapters.base import BaseOutputSink, SiteConfiguration
from egregora.output_adapters.conventions import RouteConfig, StandardUrlConvention
from egregora.output_adapters.mkdocs.paths import compute_site_prefix, derive_mkdocs_paths
from egregora.output_adapters.mkdocs.scaffolding import MkDocsSiteScaffolder, safe_yaml_load
from egregora.utils.datetime_utils import parse_datetime_flexible
from egregora.utils.filesystem import ensure_author_entries
from egregora.utils.frontmatter_utils import parse_frontmatter
from egregora.utils.paths import slugify

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

    def __init__(self) -> None:
        """Initializes the adapter."""
        self._scaffolder = MkDocsSiteScaffolder()
        self._initialized = False
        self.site_root = None
        self._url_convention = StandardUrlConvention()
        self._index: dict[str, Path] = {}
        self._ctx: UrlContext | None = None

    def initialize(self, site_root: Path, url_context: UrlContext | None = None) -> None:
        """Initializes the adapter with all necessary paths and dependencies."""
        site_paths = derive_mkdocs_paths(site_root)
        self.site_root = site_paths["site_root"]
        self._site_root = self.site_root
        self.docs_dir = site_paths["docs_dir"]
        prefix = compute_site_prefix(self.site_root, site_paths["docs_dir"])
        self._ctx = url_context or UrlContext(base_url="", site_prefix=prefix, base_path=self.site_root)
        self.posts_dir = site_paths["posts_dir"]
        # UNIFIED: Everything goes to posts_dir now
        self.profiles_dir = self.posts_dir
        self.journal_dir = self.posts_dir
        self.media_dir = site_paths["media_dir"]
        # Note: urls_dir removed - enrichment URLs now go to posts_dir

        self.posts_dir.mkdir(parents=True, exist_ok=True)
        # profiles_dir and journal_dir point to posts_dir, so no need to mkdir them separately
        self.media_dir.mkdir(parents=True, exist_ok=True)

        # Configure URL convention to match filesystem layout
        # This ensures that generated URLs align with where files are actually stored
        routes = RouteConfig(
            posts_prefix=self.posts_dir.relative_to(self.docs_dir).as_posix(),
            profiles_prefix=self.profiles_dir.relative_to(self.docs_dir).as_posix(),
            media_prefix=self.media_dir.relative_to(self.docs_dir).as_posix(),
            journal_prefix=self.journal_dir.relative_to(self.docs_dir).as_posix(),
        )
        self._url_convention = StandardUrlConvention(routes)

        self._initialized = True

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
            author_uuid: Full or partial UUID of the author
            
        Returns:
            Path to author's folder (created if doesn't exist)
        """
        # Use first 16 chars of UUID for shorter folder names
        short_uuid = author_uuid[:16] if len(author_uuid) > 16 else author_uuid
        author_dir = self.posts_dir / "authors" / short_uuid
        author_dir.mkdir(parents=True, exist_ok=True)
        return author_dir


    def persist(self, document: Document) -> None:  # noqa: C901
        doc_id = document.document_id
        url = self._url_convention.canonical_url(document, self._ctx)
        path = self._url_to_path(url, document)

        if doc_id in self._index:
            old_path = self._index[doc_id]
            if old_path != path and old_path.exists():
                logger.info("Moving document %s: %s → %s", doc_id[:8], old_path, path)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    old_path.unlink()
                else:
                    old_path.rename(path)

        if path.exists() and document.type == DocumentType.ENRICHMENT_URL:
            existing_doc_id = self._get_document_id_at_path(path)
            if existing_doc_id and existing_doc_id != doc_id:
                path = self._resolve_collision(path, doc_id)
                logger.warning("Hash collision for %s, using %s", doc_id[:8], path)

        path.parent.mkdir(parents=True, exist_ok=True)

        match document.type:
            case DocumentType.POST:
                self._write_post_doc(document, path)
            case DocumentType.JOURNAL:
                self._write_journal_doc(document, path)
            case DocumentType.PROFILE:
                self._write_profile_doc(document, path)
            case DocumentType.ENRICHMENT_URL | DocumentType.ENRICHMENT_MEDIA:
                self._write_enrichment_doc(document, path)
            case DocumentType.MEDIA:
                self._write_media_doc(document, path)
            case _:
                self._write_generic_doc(document, path)

        self._index[doc_id] = path
        logger.debug("Served document %s at %s", doc_id, path)

    def _resolve_document_path(self, doc_type: DocumentType, identifier: str) -> Path | None:  # noqa: PLR0911
        """Resolve filesystem path for a document based on its type.

        UNIFIED: Posts, profiles, journals, and enrichment URLs all live in posts_dir.
        We distinguish them by filename patterns and category metadata.

        Args:
            doc_type: Type of document
            identifier: Document identifier

        Returns:
            Path to document or None if type unsupported

        """
        match doc_type:
            case DocumentType.PROFILE:
                # Profiles: simple filename (e.g., "user-123.md")
                return self.posts_dir / f"{identifier}.md"
            case DocumentType.POST:
                # Posts: dated filename (e.g., "2024-01-01-slug.md")
                matches = list(self.posts_dir.glob(f"*-{identifier}.md"))
                if matches:
                    return max(matches, key=lambda p: p.stat().st_mtime)
                return None
            case DocumentType.JOURNAL:
                # Journals: simple filename with slug
                return self.posts_dir / f"{identifier.replace('/', '-')}.md"
            case DocumentType.ENRICHMENT_URL:
                # Enrichment URLs: now in posts_dir (unified)
                return self.posts_dir / f"{identifier}.md"
            case DocumentType.ENRICHMENT_MEDIA:
                # Enrichment media: stays in media_dir
                return self.media_dir / f"{identifier}.md"
            case DocumentType.MEDIA:
                # Media files: stay in media_dir
                return self.media_dir / identifier
            case _:
                return None

    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:
        path = self._resolve_document_path(doc_type, identifier)

        if path is None or not path.exists():
            logger.debug(
                "Document not found: %s/%s",
                doc_type.value if isinstance(doc_type, DocumentType) else doc_type,
                identifier,
            )
            return None

        try:
            if doc_type == DocumentType.MEDIA:
                raw_bytes = path.read_bytes()
                metadata = {"filename": path.name}
                return Document(content=raw_bytes, type=doc_type, metadata=metadata)
            content = path.read_text(encoding="utf-8")
            metadata, actual_content = parse_frontmatter(content)
        except OSError:
            logger.exception("Failed to read document at %s", path)
            return None

        return Document(content=actual_content, type=doc_type, metadata=metadata)

    def validate_structure(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file.

        Implements SiteScaffolder.validate_structure.
        """
        return self.supports_site(site_root)

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file."""
        return self._scaffolder.supports_site(site_root)

    def scaffold_site(self, site_root: Path, site_name: str, **_kwargs: object) -> tuple[Path, bool]:
        """Create or update an MkDocs site using the dedicated scaffolder."""
        return self._scaffolder.scaffold_site(site_root, site_name, **_kwargs)

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
        # Use derive_mkdocs_paths to find mkdocs.yml (checks .egregora/, root)
        site_paths = derive_mkdocs_paths(site_root)
        mkdocs_path = site_paths.get("mkdocs_path")
        if not mkdocs_path:
            msg = f"No mkdocs.yml found in {site_root}"
            raise FileNotFoundError(msg)
        try:
            config = safe_yaml_load(mkdocs_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse mkdocs.yml at %s: %s", mkdocs_path, exc)
            config = {}
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

    def documents(self) -> Iterator[Document]:
        """Return all MkDocs documents as Document instances (lazy iterator)."""
        if not hasattr(self, "_site_root") or self._site_root is None:
            return

        # DRY: Use list() to scan directories, then get() to load content
        # Note: list() returns metadata where identifier is a relative path (e.g., "posts/slug.md")
        # but get() expects a simpler identifier for some types (e.g., "slug" for posts).
        # To reliably load all listed documents, we bypass the identifier resolution logic
        # and load directly from the known path found by list().
        for meta in self.list():
            if meta.doc_type and "path" in meta.metadata:
                doc_path = Path(str(meta.metadata["path"]))
                # Bypass identifier resolution by loading directly from path
                doc = self._document_from_path(doc_path, meta.doc_type)
                if doc:
                    yield doc

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

        # UNIFIED: Scan posts_dir once, detect types by category metadata
        # profiles_dir and journal_dir now point to posts_dir, so we only scan once
        yield from self._list_from_unified_dir(self.posts_dir, doc_type)

        # Media and enrichment media stay in separate directories
        yield from self._list_from_dir(
            self._site_root / "docs" / "media",
            DocumentType.ENRICHMENT_MEDIA,
            doc_type,
            recursive=True,
            exclude_names={"index.md"},
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
            raise RuntimeError(msg)

        # MkDocs identifiers are relative paths from site_root
        return (self._site_root / identifier).resolve()

    # REMOVED: finalize_window() logic for profile regeneration.
    # Rationale: Profile regeneration is now handled by the ProfileWorker and site_generator.py
    # which aggregates stats dynamically. The adapter should focus on persistence (OutputSink)
    # and not orchestration logic.

    # def finalize_window(
    #    self,
    #    window_label: str,
    #    posts_created: list[str],
    #    profiles_updated: list[str],
    #    metadata: dict[str, Any] | None = None,
    # ) -> None:
    #    """Post-processing hook called after writer agent completes a window.
    #
    #    Regenerates the profiles index page to include any newly created or updated profiles.
    #    """
    #    ...

    @staticmethod
    def _detect_document_type_from_metadata(path: Path) -> DocumentType:
        """Detect document type by reading category metadata from file.

        Returns the appropriate DocumentType based on categories in frontmatter.
        Falls back to POST for documents without category metadata.
        """
        try:
            content = path.read_text(encoding="utf-8")
            metadata, _ = parse_frontmatter(content)

            if not metadata:
                # No frontmatter, assume POST
                return DocumentType.POST

            categories = metadata.get("categories", [])
            if not isinstance(categories, list):
                categories = []

            # Detect by category
            if "Authors" in categories:
                return DocumentType.PROFILE
            if "Journal" in categories:
                return DocumentType.JOURNAL
            if "Enrichment" in categories:
                return DocumentType.ENRICHMENT_URL
            # Default to POST (including posts without categories)
            return DocumentType.POST

        except (OSError, yaml.YAMLError):
            # If we can't read/parse, assume POST
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
                detected_type = self._detect_document_type_from_metadata(path)

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

    def _document_from_path(self, path: Path, doc_type: DocumentType) -> Document | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        metadata, body = parse_frontmatter(raw)
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

    def _url_to_path(self, url: str, document: Document) -> Path:  # noqa: PLR0911
        base = self._ctx.base_url.rstrip("/")
        if url.startswith(base):
            url_path = url[len(base) :]
        else:
            url_path = url

        url_path = url_path.strip("/")

        match document.type:
            case DocumentType.POST:
                # Route to author folder if authors exist in metadata
                authors = document.metadata.get("authors", [])
                if authors:
                    # Extract UUID from first author (primary author)
                    if isinstance(authors[0], dict):
                        author_uuid = authors[0].get("uuid")
                    else:
                        author_uuid = authors[0]
                    
                    if author_uuid:
                        author_dir = self._get_author_dir(author_uuid)
                        slug = url_path.split("/")[-1]
                        return author_dir / f"{slug}.md"
                
                # Fallback to top-level posts/
                return self.posts_dir / f"{url_path.split('/')[-1]}.md"
            case DocumentType.PROFILE:
                # UNIFIED: profiles go to posts_dir now
                return self.posts_dir / f"{url_path.split('/')[-1]}.md"
            case DocumentType.JOURNAL:
                # When url_path is just "journal" (root journal URL), return journal.md in docs root
                # Otherwise, extract the slug and put it in journal/
                # UNIFIED: Journal entries go to posts_dir now.
                slug = url_path.split("/")[-1]
                if url_path == "journal":
                    return self.docs_dir / "journal.md"
                return self.posts_dir / f"{slug}.md"
            case DocumentType.ENRICHMENT_URL:
                # url_path might be 'media/urls/slug' -> we want 'slug.md' inside urls_dir
                # UNIFIED: Enrichment URLs -> posts_dir
                slug = url_path.split("/")[-1]
                return self.posts_dir / f"{slug}.md"
            case DocumentType.ENRICHMENT_MEDIA:
                # url_path is like 'media/images/foo' -> we want 'docs/media/images/foo.md'
                rel_path = self._strip_media_prefix(url_path)
                return self.media_dir / f"{rel_path}.md"
            case DocumentType.MEDIA:
                rel_path = self._strip_media_prefix(url_path)
                return self.media_dir / rel_path
            case _:
                return self._resolve_generic_path(url_path)

    def _resolve_generic_path(self, url_path: str) -> Path:
        return self.site_root / f"{url_path}.md"

    def _strip_media_prefix(self, url_path: str) -> str:
        """Helper to strip media prefixes from URL path."""
        rel_path = url_path
        media_prefix = self._ctx.site_prefix + "/media" if self._ctx.site_prefix else "media"
        if rel_path.startswith(media_prefix):
            rel_path = rel_path[len(media_prefix) :].strip("/")
        elif rel_path.startswith("media/"):
            rel_path = rel_path[6:]
        return rel_path

    def _get_author_dir(self, author_uuid: str) -> Path:
        """Get the directory for a given author UUID."""
        author_dir = self.posts_dir / "authors" / author_uuid
        author_dir.mkdir(parents=True, exist_ok=True)
        return author_dir

    def _parse_frontmatter(self, path: Path) -> dict:
        """Extract YAML frontmatter from markdown file.
        
        Args:
            path: Path to markdown file
            
        Returns:
            Dictionary of frontmatter metadata (empty if none found)
        """
        try:
            content = path.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return yaml.safe_load(parts[1]) or {}
        except Exception as e:
            logger.warning(f"Failed to parse frontmatter from {path}: {e}")
        return {}

    # Document Writing Strategies ---------------------------------------------

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

    def _write_post_doc(self, document: Document, path: Path) -> None:
        metadata = dict(document.metadata or {})

        # Posts don't need a forced category - Material blog shows uncategorized posts in main feed
        # But ensure categories is a list if present
        if "categories" in metadata and not isinstance(metadata["categories"], list):
            metadata["categories"] = []

        if "date" in metadata:
            # Parse to datetime object for proper YAML serialization (unquoted)
            # Material blog plugin requires native datetime type, not string
            dt = parse_datetime_flexible(metadata["date"])
            if dt:
                metadata["date"] = dt
        if "authors" in metadata:
            ensure_author_entries(path.parent, metadata.get("authors"))

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

        yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
        full_content = f"---\n{yaml_front}---\n\n{document.content}"
        path.write_text(full_content, encoding="utf-8")

    def _write_journal_doc(self, document: Document, path: Path) -> None:
        metadata = self._ensure_hidden(dict(document.metadata or {}))

        # Add type for categorization
        metadata["type"] = "journal"

        # Add Journal category using helper (handles malformed data)
        metadata = self._ensure_category(metadata, "Journal")

        yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
        full_content = f"---\n{yaml_front}---\n\n{document.content}"
        path.write_text(full_content, encoding="utf-8")

    def _write_profile_doc(self, document: Document, path: Path) -> None:
        # Ensure UUID is in metadata
        author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
        if not author_uuid:
            msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
            raise ValueError(msg)

        # Use standard frontmatter writing logic
        metadata = dict(document.metadata or {})

        # Add type for categorization
        metadata["type"] = "profile"

        # Ensure avatar is present (fallback if needed)
        if "avatar" not in metadata:
            metadata["avatar"] = generate_fallback_avatar_url(author_uuid)

        # Add Authors category using helper (handles malformed data)
        metadata = self._ensure_category(metadata, "Authors")

        yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)

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

        # Prepend avatar using MkDocs macros syntax
        # This matches the logic in profiles.py but ensures it happens even when writing via adapter
        # Note: We use double braces {{ }} for Jinja2 syntax, so in f-string we need quadruple braces {{{{ }}}}
        content_with_avatar = (
            f"![Avatar]({{{{ page.meta.avatar }}}}){{ align=left width=150 }}\n\n{document.content}"
        )

        full_content = f"---\n{yaml_front}---\n\n{content_with_avatar}"
        path.write_text(full_content, encoding="utf-8")

    def _write_enrichment_doc(self, document: Document, path: Path) -> None:
        metadata = self._ensure_hidden(document.metadata.copy())
        metadata.setdefault("document_type", document.type.value)
        metadata.setdefault("slug", document.slug)
        if document.parent_id:
            metadata.setdefault("parent_id", document.parent_id)
        if document.parent and document.parent.metadata.get("slug"):
            metadata.setdefault("parent_slug", document.parent.metadata.get("slug"))

        # Add Enrichment category using helper (handles malformed data)
        metadata = self._ensure_category(metadata, "Enrichment")

        yaml_front = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
        full_content = f"---\n{yaml_front}---\n\n{document.content}"
        path.write_text(full_content, encoding="utf-8")

    def _write_media_doc(self, document: Document, path: Path) -> None:
        if document.metadata.get("pii_deleted"):
            logger.info("Skipping persistence of PII-containing media: %s", path.name)
            return

        payload = (
            document.content if isinstance(document.content, bytes) else document.content.encode("utf-8")
        )
        path.write_bytes(payload)

    def _write_generic_doc(self, document: Document, path: Path) -> None:
        if isinstance(document.content, bytes):
            path.write_bytes(document.content)
        else:
            path.write_text(document.content, encoding="utf-8")

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

    def _get_document_id_at_path(self, path: Path) -> str | None:
        if not path.exists():
            return None

        try:
            raw_content = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read existing document at %s: %s", path, exc)
            return None

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
                msg = f"Failed to resolve collision for {path} after {max_attempts} attempts"
                raise RuntimeError(msg)

    # ============================================================================
    # Phase 2: Dynamic Data Population for UX Templates
    # ============================================================================

    def get_site_stats(self) -> dict[str, int]:
        """Calculate site statistics for homepage.

        Returns:
            Dictionary with post_count, profile_count, media_count, journal_count

        """
        stats = {
            "post_count": 0,
            "profile_count": 0,
            "media_count": 0,
            "journal_count": 0,
        }

        if not hasattr(self, "posts_dir") or not self.posts_dir:
            return stats

        # Count posts (exclude index.md and tags.md)
        if self.posts_dir.exists():
            stats["post_count"] = len(
                [p for p in self.posts_dir.glob("*.md") if p.name not in {"index.md", "tags.md"}]
            )

        # Count profiles (exclude index.md)
        if self.profiles_dir.exists():
            stats["profile_count"] = len([p for p in self.profiles_dir.glob("*.md") if p.name != "index.md"])

        # Count media (URLs + images + videos + audio - exclude indexes)
        if self.media_dir.exists():
            all_media = list(self.media_dir.rglob("*.md"))
            stats["media_count"] = len([p for p in all_media if p.name != "index.md"])

        # Count journal entries (exclude index.md)
        if self.journal_dir.exists():
            stats["journal_count"] = len([p for p in self.journal_dir.glob("*.md") if p.name != "index.md"])

        return stats

    def get_profiles_data(self) -> list[dict[str, Any]]:
        """Extract profile metadata for profiles index, including calculated stats."""
        profiles = []
        all_posts = list(self.documents())  # Inefficient, but necessary for stats

        if not hasattr(self, "profiles_dir") or not self.profiles_dir.exists():
            return profiles

        for profile_path in sorted(self.profiles_dir.glob("[!index]*.md")):
            try:
                content = profile_path.read_text(encoding="utf-8")
                metadata, _ = parse_frontmatter(content)
                author_uuid = profile_path.stem

                author_posts = [
                    post
                    for post in all_posts
                    if post.metadata and author_uuid in post.metadata.get("authors", [])
                ]

                post_count = len(author_posts)
                word_count = sum(len(post.content.split()) for post in author_posts)

                topics = {}
                for post in author_posts:
                    for tag in post.metadata.get("tags", []):
                        topics[tag] = topics.get(tag, 0) + 1

                top_topics = sorted(topics.items(), key=lambda item: item[1], reverse=True)

                avatar = metadata.get("avatar", "")
                # Generate fallback avatar if missing
                if not avatar:
                    avatar = generate_fallback_avatar_url(author_uuid)

                profiles.append(
                    {
                        "uuid": author_uuid,
                        "name": metadata.get("name", author_uuid[:8]),
                        "avatar": avatar,
                        "bio": metadata.get("bio", "Profile pending - first contributions detected"),
                        "post_count": post_count,
                        "word_count": word_count,
                        "topics": [topic for topic, count in top_topics],
                        "topic_counts": top_topics,
                        "member_since": metadata.get("member_since", "2024"),  # Placeholder
                    }
                )
            except (OSError, yaml.YAMLError) as e:
                logger.warning("Failed to parse profile %s: %s", profile_path, e)
                continue

        return profiles

    def get_recent_media(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recent media items for media index.

        UNIFIED: Enrichment URLs now live in posts_dir with "Enrichment" category.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of media dictionaries with title, url, slug, summary

        """
        media_items = []

        if not hasattr(self, "posts_dir") or not self.posts_dir.exists():
            return media_items

        # Get all files from posts_dir, filter for Enrichment category
        all_files = list(self.posts_dir.glob("*.md"))
        enrichment_files = []

        for path in all_files:
            try:
                # Check if file has Enrichment category
                doc_type = self._detect_document_type_from_metadata(path)
                if doc_type == DocumentType.ENRICHMENT_URL:
                    enrichment_files.append(path)
            except (OSError, yaml.YAMLError):
                continue

        # Sort by modification time (newest first) and limit
        url_files = sorted(enrichment_files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

        for media_path in url_files:
            try:
                content = media_path.read_text(encoding="utf-8")
                metadata, body = parse_frontmatter(content)

                # Extract summary from content
                summary = ""
                if "## Summary" in body:
                    summary_part = body.split("## Summary", 1)[1].split("##", 1)[0]
                    summary = summary_part.strip()[:200]

                media_items.append(
                    {
                        "title": metadata.get("title", media_path.stem),
                        "url": metadata.get("url", ""),
                        "slug": metadata.get("slug", media_path.stem),
                        "summary": summary or metadata.get("description", ""),
                    }
                )
            except (OSError, yaml.YAMLError) as e:
                logger.warning("Failed to parse media %s: %s", media_path, e)
                continue

        return media_items

    def _append_author_cards(self, content: str, author_ids: list[str]) -> str:
        """Append author cards to post content using Jinja template.

        Args:
            content: Post markdown content
            author_ids: List of author UUIDs

        Returns:
            Content with author cards appended

        """
        if not author_ids:
            return content

        # Load .authors.yml
        authors_file = None
        if hasattr(self, "site_root") and self.site_root:
            for potential_path in [
                self.site_root / "docs" / ".authors.yml",
                self.site_root / ".authors.yml",
            ]:
                if potential_path.exists():
                    authors_file = potential_path
                    break

        if not authors_file:
            return content

        try:
            with authors_file.open("r", encoding="utf-8") as f:
                authors_db = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to load .authors.yml: %s", e)
            return content

        # Build author data for template
        authors_data = []
        for author_id in author_ids:
            author = authors_db.get(author_id, {})
            name = author.get("name", author_id[:8])
            avatar = author.get("avatar", "")

            # Generate fallback avatar if not set
            if not avatar:
                avatar = generate_fallback_avatar_url(author_id)

            authors_data.append(
                {
                    "uuid": author_id,
                    "name": name,
                    "avatar": avatar,
                }
            )

        # Render using Jinja template
        try:
            templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())
            template = env.get_template("partials/author_cards.jinja")
            author_cards_html = template.render(authors=authors_data)
            return content.rstrip() + "\n" + author_cards_html
        except (OSError, TemplateError) as e:
            logger.warning("Failed to render author cards template: %s", e)
            return content

    def regenerate_tags_page(self) -> None:
        """Regenerate the tags.md page with current tag frequencies for word cloud visualization.

        Collects all tags from posts, calculates frequencies, and renders an updated
        tags page with interactive word cloud and alphabetical list.
        """
        if not hasattr(self, "posts_dir") or not self.posts_dir.exists():
            logger.debug("Posts directory not found, skipping tags page regeneration")
            return

        # Collect all tags from posts
        tag_counts: Counter = Counter()
        all_posts = list(self.documents())

        for post in all_posts:
            if post.type != DocumentType.POST:
                continue
            tags = post.metadata.get("tags", [])
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    tag_counts[tag.strip()] += 1

        if not tag_counts:
            logger.info("No tags found in posts, skipping tags page regeneration")
            return

        # Calculate frequency levels (1-10 scale) for word cloud sizing
        max_count = max(tag_counts.values())
        min_count = min(tag_counts.values())
        count_range = max_count - min_count if max_count > min_count else 1

        tags_data = []
        for tag_name, count in tag_counts.items():
            # Normalize to 1-10 scale for CSS data-frequency attribute
            if count_range > 0:
                frequency_level = int(((count - min_count) / count_range) * 9) + 1
            else:
                frequency_level = 5  # Middle value if all tags have same count

            tags_data.append(
                {
                    "name": tag_name,
                    "slug": slugify(tag_name),
                    "count": count,
                    "frequency_level": min(10, max(1, frequency_level)),
                }
            )

        # Sort by count (descending) for word cloud
        tags_data.sort(key=lambda x: x["count"], reverse=True)

        # Render the tags page template
        try:
            templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

            template = env.get_template("docs/posts/tags.md.jinja")
            content = template.render(
                tags=tags_data,
                generated_date=datetime.now(UTC).strftime("%Y-%m-%d"),
            )

            tags_path = self.posts_dir / "tags.md"
            tags_path.write_text(content, encoding="utf-8")
            logger.info("Regenerated tags page with %d unique tags", len(tags_data))

        except (OSError, TemplateError):
            logger.exception("Failed to regenerate tags page")


# ============================================================================
# MkDocs filesystem storage helpers
# ============================================================================

ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)


# Author Profile Generation (Append-Only) ---------------------------------

def _build_author_profile(self, author_uuid: str) -> dict | None:
    """Build author profile by scanning all their posts chronologically.
    
    Sequential metadata updates: later posts override earlier values.
    
    Args:
        author_uuid: UUID of the author
        
    Returns:
        Profile dictionary with derived state, or None if no posts found
    """
    author_dir = self.posts_dir / "authors" / author_uuid[:16]
    if not author_dir.exists():
        return None
    
    posts = sorted(author_dir.glob("*.md"), key=lambda p: p.stem)
    
    profile = {
        "uuid": author_uuid,
        "name": None,
        "bio": None,
        "avatar": None,
        "interests": set(),
        "posts": [],
    }
    
    for post_path in posts:
        if post_path.name == "index.md":
            continue
        
        frontmatter = self._parse_frontmatter(post_path)
        authors = frontmatter.get("authors", [])
        
        # Find this author's metadata in the post
        for author in authors:
            if isinstance(author, dict):
                author_uuid_in_post = author.get("uuid", "")
                if author_uuid_in_post.startswith(author_uuid[:16]):
                    # Sequential merge: later values win
                    if "name" in author:
                        profile["name"] = author["name"]
                    if "bio" in author:
                        profile["bio"] = author["bio"]
                    if "avatar" in author:
                        profile["avatar"] = author["avatar"]
                    if "interests" in author:
                        profile["interests"].update(author["interests"])
        
        # Track this post
        profile["posts"].append({
            "title": frontmatter.get("title", post_path.stem),
            "date": frontmatter.get("date", ""),
            "slug": post_path.stem,
            "path": post_path,
        })
    
    if not profile["name"]:
        return None  # No valid profile without a name
    
    profile["interests"] = sorted(profile["interests"])
    return profile

def _render_author_index(self, profile: dict) -> str:
    """Render author index.md content from profile data.
    
    Args:
        profile: Profile dictionary with derived state
        
    Returns:
        Markdown content for index.md
    """
    # Generate avatar HTML if available
    avatar_html = ""
    if profile.get("avatar"):
        avatar_html = f"![Avatar]({profile['avatar']}){{ align=left width=150 }}\n\n"
    
    # Build post list (newest first)
    posts_md = "\n".join([
        f"- [{p['title']}]({p['slug']}.md) - {p['date']}"
        for p in reversed(profile["posts"])
    ])
    
    # Build frontmatter
    frontmatter = f"""---
title: {profile['name']}
type: profile
uuid: {profile['uuid']}
avatar: {profile.get('avatar', '')}
bio: {profile.get('bio', '')}
interests: {profile.get('interests', [])}
---

{avatar_html}# {profile['name']}

{profile.get('bio', '')}

## Posts ({len(profile['posts'])})

{posts_md}

## Interests

{', '.join(profile.get('interests', []))}
"""
    return frontmatter

def _sync_author_profiles(self) -> None:
    """Generate index.md for all authors from derived state."""
    authors_dir = self.posts_dir / "authors"
    if not authors_dir.exists():
        logger.info("No authors directory found, skipping profile sync")
        return
    
    authors_synced = 0
    for author_dir in authors_dir.glob("*/"):
        uuid = author_dir.name
        profile = self._build_author_profile(uuid)
        
        if not profile:
            logger.warning(f"Skipping author {uuid}: no valid profile data")
            continue
        
        # Render and write index.md
        content = self._render_author_index(profile)
        index_path = author_dir / "index.md"
        index_path.write_text(content, encoding="utf-8")
        
        authors_synced += 1
        logger.info(f"Generated profile for {profile['name']} ({uuid})")
    
    logger.info(f"Synced {authors_synced} author profiles")



# ============================================================================
# MkDocs filesystem storage helpers
# ============================================================================

# Moved to src/egregora/utils/filesystem.py


def secure_path_join(base_dir: Path, user_path: str) -> Path:
    """Safely join ``user_path`` to ``base_dir`` preventing directory traversal."""
    full_path = (base_dir / user_path).resolve()
    try:
        full_path.relative_to(base_dir.resolve())
    except ValueError as exc:
        msg = f"Path traversal detected: {user_path!r} escapes base directory {base_dir}"
        raise ValueError(msg) from exc
    return full_path
