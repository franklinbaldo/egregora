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
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from egregora.config.settings import EgregoraConfig
from egregora.data_primitives import DocumentMetadata
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlContext, UrlConvention
from egregora.output_adapters.base import OutputAdapter, SiteConfiguration
from egregora.output_adapters.conventions import StandardUrlConvention
from egregora.output_adapters.mkdocs.paths import compute_site_prefix, derive_mkdocs_paths
from egregora.output_adapters.mkdocs.scaffolding import (
    MkDocsSiteScaffolder,
    load_egregora_config,
    safe_yaml_load,
)
from egregora.output_adapters.mkdocs.site_generator import (
    _append_author_cards,
    get_profiles_data,
    get_recent_media,
    get_site_stats,
)
from egregora.utils.filesystem import (
    ensure_author_entries,
    format_frontmatter_datetime,
)
from egregora.utils.frontmatter_utils import parse_frontmatter
from egregora.utils.paths import slugify

logger = logging.getLogger(__name__)


class MkDocsAdapter(OutputAdapter):
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

        # Dispatch tables for strategy pattern
        self._path_resolvers = {
            DocumentType.POST: self._resolve_post_path,
            DocumentType.PROFILE: self._resolve_profile_path,
            DocumentType.JOURNAL: self._resolve_journal_path,
            DocumentType.ENRICHMENT_URL: self._resolve_enrichment_url_path,
            DocumentType.ENRICHMENT_MEDIA: self._resolve_enrichment_media_path,
            DocumentType.MEDIA: self._resolve_media_path,
        }

        self._writers = {
            DocumentType.POST: self._write_post_doc,
            DocumentType.JOURNAL: self._write_journal_doc,
            DocumentType.PROFILE: self._write_profile_doc,
            DocumentType.ENRICHMENT_URL: self._write_enrichment_doc,
            DocumentType.ENRICHMENT_MEDIA: self._write_enrichment_doc,
            DocumentType.MEDIA: self._write_media_doc,
        }

    def initialize(self, site_root: Path, url_context: UrlContext | None = None) -> None:
        """Initializes the adapter with all necessary paths and dependencies."""
        try:
            config_dict = load_egregora_config(site_root)
            config = EgregoraConfig(**config_dict) if config_dict else EgregoraConfig()
        except Exception:
            # Fallback to default config if loading fails (e.g. during init)
            logger.debug("Could not load config for initialization, using defaults")
            config = EgregoraConfig()

        site_paths = derive_mkdocs_paths(site_root, config=config)
        self.site_root = site_paths["site_root"]
        self._site_root = self.site_root
        self.docs_dir = site_paths["docs_dir"]
        prefix = compute_site_prefix(self.site_root, site_paths["docs_dir"])
        self._ctx = url_context or UrlContext(base_url="", site_prefix=prefix, base_path=self.site_root)
        self.posts_dir = site_paths["posts_dir"]
        self.profiles_dir = site_paths["profiles_dir"]
        self.journal_dir = site_paths["journal_dir"]
        self.media_dir = site_paths["media_dir"]
        self.urls_dir = self.media_dir / "urls"

        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.urls_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
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

    def persist(self, document: Document) -> None:
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

        self._write_document(document, path)
        self._index[doc_id] = path
        logger.debug("Served document %s at %s", doc_id, path)

    def _resolve_document_path(self, doc_type: DocumentType, identifier: str) -> Path | None:
        """Resolve filesystem path for a document based on its type.

        Args:
            doc_type: Type of document
            identifier: Document identifier

        Returns:
            Path to document or None if type unsupported

        """
        # Dispatch table for document type to path resolution
        path_resolvers = {
            DocumentType.PROFILE: lambda: self.profiles_dir / f"{identifier}.md",
            DocumentType.POST: lambda: (
                max(self.posts_dir.glob(f"*-{identifier}.md"), key=lambda p: p.stat().st_mtime)
                if (_matches := list(self.posts_dir.glob(f"*-{identifier}.md")))
                else None
            ),
            DocumentType.JOURNAL: lambda: self.journal_dir / f"{identifier.replace('/', '-')}.md",
            DocumentType.ENRICHMENT_URL: lambda: self.urls_dir / f"{identifier}.md",
            DocumentType.ENRICHMENT_MEDIA: lambda: self.media_dir / f"{identifier}.md",
            DocumentType.MEDIA: lambda: self.media_dir / identifier,
        }

        resolver = path_resolvers.get(doc_type)
        return resolver() if resolver else None

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

        # Scan directories and yield DocumentMetadata
        yield from self._list_from_dir(self.posts_dir, DocumentType.POST, doc_type)
        yield from self._list_from_dir(self.profiles_dir, DocumentType.PROFILE, doc_type)
        yield from self._list_from_dir(
            self._site_root / "docs" / "media",
            DocumentType.ENRICHMENT_MEDIA,
            doc_type,
            recursive=True,
            exclude_names={"index.md"},
        )
        yield from self._list_from_dir(
            self.media_dir / "urls", DocumentType.ENRICHMENT_URL, doc_type, recursive=True
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

    def _list_from_dir(
        self,
        directory: Path,
        dtype: DocumentType,
        filter_type: DocumentType | None = None,
        *,
        recursive: bool = False,
        exclude_names: set[str] | None = None,
    ) -> Iterator[DocumentMetadata]:
        """Helper to yield DocumentMetadata from a directory."""
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

    def _url_to_path(self, url: str, document: Document) -> Path:
        base = self._ctx.base_url.rstrip("/")
        if url.startswith(base):
            url_path = url[len(base) :]
        else:
            url_path = url

        url_path = url_path.strip("/")

        # Use strategy pattern to resolve path based on document type
        resolver = self._path_resolvers.get(document.type, self._resolve_generic_path)
        return resolver(url_path)

    # Path Resolution Strategies ----------------------------------------------

    def _resolve_post_path(self, url_path: str) -> Path:
        return self.posts_dir / f"{url_path.split('/')[-1]}.md"

    def _resolve_profile_path(self, url_path: str) -> Path:
        return self.profiles_dir / f"{url_path.split('/')[-1]}.md"

    def _resolve_journal_path(self, url_path: str) -> Path:
        # When url_path is just "journal" (root journal URL), return journal.md in docs root
        # Otherwise, extract the slug and put it in journal/
        slug = url_path.split("/")[-1]
        if url_path == "journal":
            return self.docs_dir / "journal.md"
        return self.journal_dir / f"{slug}.md"

    def _resolve_enrichment_url_path(self, url_path: str) -> Path:
        # url_path might be 'media/urls/slug' -> we want 'slug.md' inside urls_dir
        slug = url_path.split("/")[-1]
        return self.urls_dir / f"{slug}.md"

    def _resolve_enrichment_media_path(self, url_path: str) -> Path:
        # url_path is like 'media/images/foo' -> we want 'docs/media/images/foo.md'
        rel_path = self._strip_media_prefix(url_path)
        return self.media_dir / f"{rel_path}.md"

    def _resolve_media_path(self, url_path: str) -> Path:
        rel_path = self._strip_media_prefix(url_path)
        return self.media_dir / rel_path

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

    def _write_document(self, document: Document, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        # Use strategy pattern to write document
        writer = self._writers.get(document.type, self._write_generic_doc)
        writer(document, path)

    # Document Writing Strategies ---------------------------------------------

    def _get_related_posts(
        self, current_post: Document, all_posts: list[Document], limit: int = 3
    ) -> list[Document]:
        """Get a list of related posts based on shared tags."""
        if not current_post.metadata or "tags" not in current_post.metadata:
            return []

        current_tags = set(current_post.metadata["tags"])
        related = []
        for post in all_posts:
            if (
                post.document_id == current_post.document_id
                or not post.metadata
                or "tags" not in post.metadata
            ):
                continue

            shared_tags = current_tags.intersection(set(post.metadata["tags"]))
            if shared_tags:
                related.append((post, len(shared_tags)))

        related.sort(key=lambda x: x[1], reverse=True)
        return [post for post, score in related[:limit]]

    def _write_post_doc(self, document: Document, path: Path) -> None:
        import yaml as _yaml

        metadata = dict(document.metadata or {})
        if "date" in metadata:
            metadata["date"] = format_frontmatter_datetime(metadata["date"])
        if "authors" in metadata:
            ensure_author_entries(path.parent, metadata.get("authors"))

        # Add related posts based on shared tags
        all_posts = list(self.documents())  # This is inefficient, but will work for now
        related_posts_docs = self._get_related_posts(document, all_posts)
        metadata["related_posts"] = [
            {
                "title": post.metadata.get("title"),
                "url": self.url_convention.canonical_url(post, self._ctx),
            }
            for post in related_posts_docs
        ]

        # Add enriched authors data

        yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
        full_content = f"---\n{yaml_front}---\n\n{document.content}"
        path.write_text(full_content, encoding="utf-8")

    def _write_journal_doc(self, document: Document, path: Path) -> None:
        import yaml as _yaml

        metadata = self._ensure_hidden(dict(document.metadata or {}))
        yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
        full_content = f"---\n{yaml_front}---\n\n{document.content}"
        path.write_text(full_content, encoding="utf-8")

    def _write_profile_doc(self, document: Document, path: Path) -> None:
        import yaml as _yaml

        from egregora.knowledge.profiles import generate_fallback_avatar_url

        # Ensure UUID is in metadata
        author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
        if not author_uuid:
            msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
            raise ValueError(msg)

        # Use standard frontmatter writing logic
        metadata = dict(document.metadata or {})

        # Ensure avatar is present (fallback if needed)
        if "avatar" not in metadata:
            metadata["avatar"] = generate_fallback_avatar_url(author_uuid)

        yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)

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
        import yaml as _yaml

        metadata = self._ensure_hidden(document.metadata.copy())
        metadata.setdefault("document_type", document.type.value)
        metadata.setdefault("slug", document.slug)
        if document.parent_id:
            metadata.setdefault("parent_id", document.parent_id)
        if document.parent and document.parent.metadata.get("slug"):
            metadata.setdefault("parent_slug", document.parent.metadata.get("slug"))

        yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
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

    def get_site_stats(self) -> dict[str, Any]:
        """Calculate statistics for the site (posts, words, authors)."""
        return get_site_stats(self)

    def get_profiles_data(self) -> list[dict[str, Any]]:
        """Get data for all author profiles for templating."""
        return get_profiles_data(self)

    def get_recent_media(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recent media items for display."""
        return get_recent_media(self, limit)

    def _append_author_cards(self, content: str, author_ids: list[str]) -> str:
        """Append author cards to post content using Jinja template.

        Args:
            content: Post markdown content
            author_ids: List of author UUIDs

        Returns:
            Content with author cards appended

        """
        # Moved to site_generator.py but still referenced? No, the plan said to move it.
        # But _write_post_doc might be calling it?
        # Let's check _write_post_doc logic below.
        # It says: # Phase 2: Add author cards to POST documents - REMOVED per user request
        # So it is commented out. I can remove this method or delegate if needed.
        # The new site_generator has _append_author_cards.
        return _append_author_cards(content, self)


# ============================================================================
# MkDocs filesystem storage helpers
# ============================================================================

ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)


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
