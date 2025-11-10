"""MkDocs output format implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from egregora.agents.shared.profiler import write_profile as write_profile_content
from egregora.config.site import load_mkdocs_config, resolve_site_paths
from egregora.init.scaffolding import ensure_mkdocs_project
from egregora.rendering.base import OutputFormat, SiteConfiguration
from egregora.utils.write_post import write_post as write_mkdocs_post

if TYPE_CHECKING:
    from pathlib import Path

    from egregora.storage import EnrichmentStorage, JournalStorage, PostStorage, ProfileStorage
logger = logging.getLogger(__name__)


class MkDocsOutputFormat(OutputFormat):
    """MkDocs output format with Material theme support.

    Creates blog sites using:
    - MkDocs static site generator
    - Material for MkDocs theme
    - Blog plugin for post management
    - YAML front matter for metadata

    Coordinates all storage operations for MkDocs-based sites and provides
    storage protocol implementations through properties.
    """

    def __init__(self) -> None:
        """Initialize MkDocsOutputFormat with uninitialized storage."""
        self._site_root: Path | None = None
        self._posts_impl: "PostStorage | None" = None
        self._profiles_impl: "ProfileStorage | None" = None
        self._journals_impl: "JournalStorage | None" = None
        self._enrichments_impl: "EnrichmentStorage | None" = None

    @property
    def format_type(self) -> str:
        """Return 'mkdocs' as the format type identifier."""
        return "mkdocs"

    def initialize(self, site_root: Path) -> None:
        """Initialize MkDocs storage implementations.

        Creates all necessary directories and initializes storage protocol
        implementations for MkDocs filesystem structure.

        Args:
            site_root: Root directory of the MkDocs site

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

        # Create storage implementations
        self._posts_impl = MkDocsPostStorage(site_root, output_format=self)
        self._profiles_impl = MkDocsProfileStorage(site_root)
        self._journals_impl = MkDocsJournalStorage(site_root)
        self._enrichments_impl = MkDocsEnrichmentStorage(site_root)

        logger.debug(f"Initialized MkDocs storage for {site_root}")

    @property
    def posts(self) -> "PostStorage":
        """Get MkDocs post storage implementation.

        Returns:
            MkDocsPostStorage instance

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._posts_impl is None:
            msg = "MkDocsOutputFormat not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._posts_impl

    @property
    def profiles(self) -> "ProfileStorage":
        """Get MkDocs profile storage implementation.

        Returns:
            MkDocsProfileStorage instance

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._profiles_impl is None:
            msg = "MkDocsOutputFormat not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._profiles_impl

    @property
    def journals(self) -> "JournalStorage":
        """Get MkDocs journal storage implementation.

        Returns:
            MkDocsJournalStorage instance

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._journals_impl is None:
            msg = "MkDocsOutputFormat not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._journals_impl

    @property
    def enrichments(self) -> "EnrichmentStorage":
        """Get MkDocs enrichment storage implementation.

        Returns:
            MkDocsEnrichmentStorage instance

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._enrichments_impl is None:
            msg = "MkDocsOutputFormat not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._enrichments_impl

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file.

        Args:
            site_root: Path to check

        Returns:
            True if mkdocs.yml exists in site_root or parent directories

        """
        if not site_root.exists():
            return False
        mkdocs_path = site_root / "mkdocs.yml"
        if mkdocs_path.exists():
            return True
        _config, mkdocs_path_found = load_mkdocs_config(site_root)
        return mkdocs_path_found is not None

    def scaffold_site(self, site_root: Path, _site_name: str, **_kwargs: object) -> tuple[Path, bool]:
        """Create the initial MkDocs site structure.

        Args:
            site_root: Root directory for the site
            site_name: Display name for the site
            **kwargs: Additional options (ignored)

        Returns:
            tuple of (mkdocs_yml_path, was_created)

        Raises:
            RuntimeError: If scaffolding fails

        """
        site_root = site_root.expanduser().resolve()
        try:
            _docs_dir, created = ensure_mkdocs_project(site_root)
        except Exception as e:
            msg = f"Failed to scaffold MkDocs site: {e}"
            raise RuntimeError(msg) from e
        mkdocs_path = site_root / "mkdocs.yml"
        return (mkdocs_path, created)

    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        """Resolve all paths for an existing MkDocs site.

        Args:
            site_root: Root directory of the site

        Returns:
            SiteConfiguration with all resolved paths

        Raises:
            ValueError: If site_root is not a valid MkDocs site
            FileNotFoundError: If required directories don't exist

        """
        if not self.supports_site(site_root):
            msg = f"{site_root} is not a valid MkDocs site (no mkdocs.yml found)"
            raise ValueError(msg)
        try:
            site_paths = resolve_site_paths(site_root)
        except Exception as e:
            msg = f"Failed to resolve site paths: {e}"
            raise RuntimeError(msg) from e
        config_file = site_paths.mkdocs_path
        # Load mkdocs.yml to get site_name
        mkdocs_config, _ = load_mkdocs_config(site_root)
        return SiteConfiguration(
            site_root=site_paths.site_root,
            site_name=mkdocs_config.get("site_name", "Egregora Site"),
            docs_dir=site_paths.docs_dir,
            posts_dir=site_paths.posts_dir,
            profiles_dir=site_paths.profiles_dir,
            media_dir=site_paths.media_dir,
            config_file=config_file,
            additional_paths={
                "rag_dir": site_paths.rag_dir,
                "enriched_dir": site_paths.enriched_dir,
                "rankings_dir": site_paths.rankings_dir,
            },
        )

    def write_post(self, content: str, metadata: dict[str, Any], output_dir: Path, **_kwargs: object) -> str:
        """Write a blog post in MkDocs format.

        Args:
            content: Markdown content of the post
            metadata: Post metadata (title, date, slug, tags, authors, summary, etc.)
            output_dir: Directory to write the post to (typically posts_dir)
            **kwargs: Additional options (ignored)

        Returns:
            Path to the written file (as string)

        Raises:
            ValueError: If required metadata is missing
            RuntimeError: If writing fails

        """
        try:
            return write_mkdocs_post(content, metadata, output_dir)
        except Exception as e:
            msg = f"Failed to write MkDocs post: {e}"
            raise RuntimeError(msg) from e

    def write_profile(
        self, author_id: str, profile_data: dict[str, Any], profiles_dir: Path, **_kwargs: object
    ) -> str:
        """Write an author profile page in MkDocs format.

        Args:
            author_id: Unique identifier for the author (UUID)
            profile_data: Profile information
                Required key: "content" - markdown content
                Optional keys: any metadata
            profiles_dir: Directory to write the profile to
            **kwargs: Additional options (ignored)

        Returns:
            Path to the written file (as string)

        Raises:
            ValueError: If author_id is invalid or content is missing
            RuntimeError: If writing fails

        """
        if not author_id:
            msg = "author_id cannot be empty"
            raise ValueError(msg)
        if isinstance(profile_data, str):
            content = profile_data
        elif "content" in profile_data:
            content = profile_data["content"]
        else:
            name = profile_data.get("name", author_id)
            bio = profile_data.get("bio", "")
            content = f"# {name}\n\n{bio}"
        try:
            return write_profile_content(author_id, content, profiles_dir)
        except Exception as e:
            msg = f"Failed to write profile: {e}"
            raise RuntimeError(msg) from e

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
        config, mkdocs_path = load_mkdocs_config(site_root)
        if mkdocs_path is None:
            msg = f"No mkdocs.yml found in {site_root} or parent directories"
            raise FileNotFoundError(msg)
        return config

    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for MkDocs Material theme.

        Returns:
            List of markdown extension identifiers

        """
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

Tags automatically create taxonomy pages where readers can browse posts by topic. Use consistent, meaningful tags across posts to build a useful taxonomy.
"""
