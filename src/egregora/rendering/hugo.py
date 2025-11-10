"""Hugo output format implementation (TEMPLATE/EXAMPLE).

This is a template showing how to implement a new output format.
To complete this implementation, you would need to:
1. Install Hugo: https://gohugo.io/installation/
2. Choose a Hugo theme
3. Implement the scaffolding and post writing logic

This template demonstrates the interface that needs to be implemented.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import ibis

from egregora.rendering.base import OutputFormat, SiteConfiguration

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table

    from egregora.storage import EnrichmentStorage, JournalStorage, PostStorage, ProfileStorage

logger = logging.getLogger(__name__)


class HugoOutputFormat(OutputFormat):
    """Hugo static site generator output format.

    Hugo uses:
    - TOML/YAML front matter for metadata
    - Content organized in content/ directory
    - Themes for styling
    - Fast build times

    Note: This is a template implementation. To use it, you need to:
    1. Install Hugo
    2. Choose and configure a theme
    3. Complete the implementation below
    """

    def __init__(self) -> None:
        """Initialize HugoOutputFormat with uninitialized storage."""
        self._site_root: Path | None = None
        self._posts_impl: PostStorage | None = None
        self._profiles_impl: ProfileStorage | None = None
        self._journals_impl: JournalStorage | None = None
        self._enrichments_impl: EnrichmentStorage | None = None

    @property
    def format_type(self) -> str:
        """Return 'hugo' as the format type identifier."""
        return "hugo"

    def initialize(self, site_root: Path) -> None:
        """Initialize Hugo storage implementations.

        Note: Currently reuses MkDocs storage as placeholder since Hugo is not priority.
        Creates all necessary directories and initializes storage protocol
        implementations for Hugo filesystem structure.

        Args:
            site_root: Root directory of the Hugo site

        Raises:
            ValueError: If site_root is invalid
            RuntimeError: If storage initialization fails

        """
        from egregora.storage.mkdocs import (
            MkDocsEnrichmentStorage,
            MkDocsJournalStorage,
            MkDocsPostStorage,
            MkDocsProfileStorage,
        )

        self._site_root = site_root

        # Create storage implementations (using MkDocs as placeholder)
        self._posts_impl = MkDocsPostStorage(site_root, output_format=self)
        self._profiles_impl = MkDocsProfileStorage(site_root)
        self._journals_impl = MkDocsJournalStorage(site_root)
        self._enrichments_impl = MkDocsEnrichmentStorage(site_root)

        logger.debug(f"Initialized Hugo storage for {site_root}")

    @property
    def posts(self) -> PostStorage:
        """Get Hugo post storage implementation.

        Returns:
            PostStorage instance (currently MkDocs placeholder)

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._posts_impl is None:
            msg = "HugoOutputFormat not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._posts_impl

    @property
    def profiles(self) -> ProfileStorage:
        """Get Hugo profile storage implementation.

        Returns:
            ProfileStorage instance (currently MkDocs placeholder)

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._profiles_impl is None:
            msg = "HugoOutputFormat not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._profiles_impl

    @property
    def journals(self) -> JournalStorage:
        """Get Hugo journal storage implementation.

        Returns:
            JournalStorage instance (currently MkDocs placeholder)

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._journals_impl is None:
            msg = "HugoOutputFormat not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._journals_impl

    @property
    def enrichments(self) -> EnrichmentStorage:
        """Get Hugo enrichment storage implementation.

        Returns:
            EnrichmentStorage instance (currently MkDocs placeholder)

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._enrichments_impl is None:
            msg = "HugoOutputFormat not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._enrichments_impl

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root is a Hugo site.

        Args:
            site_root: Path to check

        Returns:
            True if config.toml or hugo.toml exists

        """
        if not site_root.exists():
            return False
        config_files = ["config.toml", "hugo.toml", "config.yaml", "hugo.yaml"]
        return any((site_root / f).exists() for f in config_files)

    def scaffold_site(
        self, site_root: Path, site_name: str, theme: str = "PaperMod", **_kwargs: object
    ) -> tuple[Path, bool]:
        """Create the initial Hugo site structure.

        Args:
            site_root: Root directory for the site
            site_name: Display name for the site
            theme: Hugo theme to use (default: PaperMod)
            **kwargs: Additional options

        Returns:
            tuple of (config_file_path, was_created)

        Raises:
            RuntimeError: If scaffolding fails
            NotImplementedError: This is a template - full implementation needed

        """
        site_root = site_root.expanduser().resolve()
        site_root.mkdir(parents=True, exist_ok=True)
        config_file = site_root / "config.toml"
        if config_file.exists():
            logger.info("Hugo site already exists at %s", site_root)
            return (config_file, False)
        (site_root / "content" / "posts").mkdir(parents=True, exist_ok=True)
        (site_root / "content" / "profiles").mkdir(parents=True, exist_ok=True)
        (site_root / "static" / "media").mkdir(parents=True, exist_ok=True)
        (site_root / "themes").mkdir(parents=True, exist_ok=True)
        (site_root / "layouts").mkdir(parents=True, exist_ok=True)
        config_content = f'baseURL = "http://localhost:1313/"\nlanguageCode = "en-us"\ntitle = "{site_name}"\ntheme = "{theme}"\n\n[params]\n  description = "Automated conversation archive"\n  author = "Egregora"\n\n[[menu.main]]\n  name = "Posts"\n  url = "/posts/"\n  weight = 1\n\n[[menu.main]]\n  name = "Profiles"\n  url = "/profiles/"\n  weight = 2\n'
        config_file.write_text(config_content, encoding="utf-8")
        logger.info("Created Hugo site at %s", site_root)
        logger.warning("Remember to install the %s theme or choose another theme!", theme)
        return (config_file, True)

    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        """Resolve all paths for an existing Hugo site.

        Args:
            site_root: Root directory of the site

        Returns:
            SiteConfiguration with all resolved paths

        Raises:
            ValueError: If site_root is not a valid Hugo site

        """
        if not self.supports_site(site_root):
            msg = f"{site_root} is not a valid Hugo site"
            raise ValueError(msg)
        config_file = None
        for filename in ["config.toml", "hugo.toml", "config.yaml", "hugo.yaml"]:
            candidate = site_root / filename
            if candidate.exists():
                config_file = candidate
                break
        content_dir = site_root / "content"
        posts_dir = content_dir / "posts"
        profiles_dir = content_dir / "profiles"
        media_dir = site_root / "static" / "media"
        return SiteConfiguration(
            site_root=site_root,
            site_name="Hugo Site",
            docs_dir=content_dir,
            posts_dir=posts_dir,
            profiles_dir=profiles_dir,
            media_dir=media_dir,
            config_file=config_file,
        )

    def write_post(self, content: str, metadata: dict[str, Any], output_dir: Path, **_kwargs: object) -> str:
        """Write a blog post in Hugo format.

        Args:
            content: Markdown content of the post
            metadata: Post metadata (title, date, slug, tags, authors, etc.)
            output_dir: Directory to write the post to
            **kwargs: Additional options

        Returns:
            Path to the written file (as string)

        Raises:
            ValueError: If required metadata is missing

        """
        required = ["title", "slug", "date"]
        for key in required:
            if key not in metadata:
                msg = f"Missing required metadata: {key}"
                raise ValueError(msg)
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = metadata["slug"]
        date_str = metadata["date"]
        filename = f"{date_str}-{slug}.md"
        filepath = output_dir / filename
        front_matter = f'''+++\ntitle = "{metadata["title"]}"\ndate = {date_str}\ndraft = false\n'''
        if "tags" in metadata:
            tags = ", ".join(f'"{t}"' for t in metadata["tags"])
            front_matter += f"tags = [{tags}]\n"
        if "summary" in metadata:
            summary = metadata["summary"].replace('"', '\\"')
            front_matter += f'description = "{summary}"\n'
        if "authors" in metadata:
            authors = ", ".join(f'"{a}"' for a in metadata["authors"])
            front_matter += f"authors = [{authors}]\n"
        front_matter += "+++\n\n"
        full_post = front_matter + content
        filepath.write_text(full_post, encoding="utf-8")
        logger.info("Wrote Hugo post to %s", filepath)
        return str(filepath)

    def write_profile(
        self, author_id: str, profile_data: dict[str, Any], profiles_dir: Path, **_kwargs: object
    ) -> str:
        """Write an author profile page in Hugo format.

        Args:
            author_id: Unique identifier for the author
            profile_data: Profile information
            profiles_dir: Directory to write the profile to
            **kwargs: Additional options

        Returns:
            Path to the written file (as string)

        """
        if not author_id:
            msg = "author_id cannot be empty"
            raise ValueError(msg)
        profiles_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(profile_data, str):
            content = profile_data
            title = author_id
        else:
            content = profile_data.get("content", "")
            title = profile_data.get("name", author_id)
        front_matter = f'+++\ntitle = "{title}"\ntype = "profile"\n+++\n\n'
        filepath = profiles_dir / f"{author_id}.md"
        filepath.write_text(front_matter + content, encoding="utf-8")
        logger.info("Wrote Hugo profile to %s", filepath)
        return str(filepath)

    def load_config(self, site_root: Path) -> dict[str, Any]:
        """Load Hugo site configuration.

        Args:
            site_root: Root directory of the site

        Returns:
            Dictionary of configuration values

        Raises:
            FileNotFoundError: If config file doesn't exist
            NotImplementedError: TOML parsing needed

        """
        for filename in ["config.toml", "hugo.toml"]:
            config_file = site_root / filename
            if config_file.exists():
                logger.warning("Hugo config parsing not fully implemented")
                return {"site_name": "Hugo Site"}
        msg = f"No Hugo config file found in {site_root}"
        raise FileNotFoundError(msg)

    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for Hugo.

        Returns:
            List of markdown extension identifiers

        """
        return [
            "tables",
            "fenced_code",
            "footnotes",
            "definition_lists",
            "strikethrough",
            "task_lists",
            "autolink",
            "typographer",
        ]

    def get_format_instructions(self) -> str:
        """Generate Hugo format instructions for the writer agent.

        Returns:
            Markdown-formatted instructions explaining Hugo conventions

        Note:
            This is a template implementation. Customize based on your Hugo theme.

        """
        return """## Output Format: Hugo

Your posts will be rendered using the Hugo static site generator.

### Front-matter Format

Use **TOML front-matter** between `+++` markers at the top of each post:

```toml
+++
title = "Your Post Title"
date = 2025-01-10
draft = false
tags = ["topic1", "topic2"]
authors = ["author-uuid"]
description = "Brief summary"
+++
```

**Alternative**: You can also use YAML front-matter (between `---` markers) if your Hugo site is configured for it.

**Required fields**: `title`, `date`, `draft`
**Optional fields**: `tags`, `authors`, `description`, `slug`

### File Naming Convention

Posts are typically named: `{date}-{slug}.md`

Examples:
- ✅ `2025-01-10-my-post.md`
- ✅ `my-post.md` (Hugo generates slug from filename)

### Content Organization

Hugo organizes content in the `content/` directory:
- `content/posts/` - Blog posts
- `content/profiles/` - Author profiles
- `static/media/` - Media files (images, videos, audio)

### Markdown Features

Hugo uses the Goldmark markdown processor by default, supporting:

- **Tables**
- **Fenced code blocks** with syntax highlighting
- **Footnotes**
- **Task lists**: `- [ ]` and `- [x]`
- **Strikethrough**: `~~text~~`
- **Autolinks**: URLs are automatically linked

### Shortcodes

Hugo supports shortcodes for rich content (theme-dependent):

```markdown
{{< figure src="/media/image.png" alt="Description" >}}
```

Consult your Hugo theme documentation for available shortcodes.

### Best Practices

1. **Set draft status**: Use `draft = false` for published posts
2. **Use tags**: Organize posts by topic
3. **Include descriptions**: Brief summaries for post listings
4. **Reference media**: Use paths relative to `/static/` directory

**Note**: This is a template. Customize based on your Hugo theme's conventions.
"""

    def list_documents(self) -> Table:  # noqa: C901, PLR0912
        """List all Hugo documents as Ibis table.

        Returns Ibis table with storage identifiers (relative paths) and modification times.
        This enables efficient delta detection using Ibis joins/filters.

        Returns:
            Ibis table with schema:
                - storage_identifier: string (relative path from site_root)
                - mtime_ns: int64 (modification time in nanoseconds)

        Example identifiers:
            - Posts: "content/posts/2025-01-10-my-post.md"
            - Profiles: "content/profiles/user-123.md"
            - Media: "static/media/images/uuid.png.md"

        """
        if not hasattr(self, "_site_root") or self._site_root is None:
            # Return empty table with correct schema
            return ibis.memtable(
                [], schema=ibis.schema({"storage_identifier": "string", "mtime_ns": "int64"})
            )

        documents = []

        # Scan posts directory
        posts_dir = self._site_root / "content" / "posts"
        if posts_dir.exists():
            for post_file in posts_dir.glob("*.md"):
                if post_file.is_file():
                    try:
                        relative_path = str(post_file.relative_to(self._site_root))
                        mtime_ns = post_file.stat().st_mtime_ns
                        documents.append({"storage_identifier": relative_path, "mtime_ns": mtime_ns})
                    except (OSError, ValueError):
                        continue

        # Scan profiles directory
        profiles_dir = self._site_root / "content" / "profiles"
        if profiles_dir.exists():
            for profile_file in profiles_dir.glob("*.md"):
                if profile_file.is_file():
                    try:
                        relative_path = str(profile_file.relative_to(self._site_root))
                        mtime_ns = profile_file.stat().st_mtime_ns
                        documents.append({"storage_identifier": relative_path, "mtime_ns": mtime_ns})
                    except (OSError, ValueError):
                        continue

        # Scan media directory (static/media)
        media_dir = self._site_root / "static" / "media"
        if media_dir.exists():
            for enrichment_file in media_dir.rglob("*.md"):
                if enrichment_file.is_file():
                    try:
                        relative_path = str(enrichment_file.relative_to(self._site_root))
                        mtime_ns = enrichment_file.stat().st_mtime_ns
                        documents.append({"storage_identifier": relative_path, "mtime_ns": mtime_ns})
                    except (OSError, ValueError):
                        continue

        # Return as Ibis table
        schema = ibis.schema({"storage_identifier": "string", "mtime_ns": "int64"})
        return ibis.memtable(documents, schema=schema)

    def resolve_document_path(self, identifier: str) -> Path:
        """Resolve Hugo storage identifier (relative path) to absolute filesystem path.

        Args:
            identifier: Relative path from site_root (e.g., "content/posts/2025-01-10-my-post.md")

        Returns:
            Path: Absolute filesystem path

        Raises:
            RuntimeError: If output format not initialized

        Example:
            >>> format.resolve_document_path("content/posts/2025-01-10-my-post.md")
            Path("/path/to/site/content/posts/2025-01-10-my-post.md")

        """
        if not hasattr(self, "_site_root") or self._site_root is None:
            msg = "HugoOutputFormat not initialized - call initialize() first"
            raise RuntimeError(msg)

        # Hugo identifiers are relative paths from site_root
        return (self._site_root / identifier).resolve()
