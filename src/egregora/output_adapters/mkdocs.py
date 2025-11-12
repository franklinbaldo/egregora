"""MkDocs output format implementation (registry-compatible).

This module contains the legacy MkDocsOutputAdapter that implements the OutputAdapter
protocol with two-phase initialization (used by the registry/factory pattern).

For the modern Document-based implementation, see mkdocs_output_adapter.py.
Storage implementations are in mkdocs_storage.py (shared with HugoOutputAdapter).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape

from egregora.agents.shared.author_profiles import write_profile as write_profile_content
from egregora.config.settings import create_default_config
from egregora.output_adapters.base import OutputAdapter, SiteConfiguration
from egregora.output_adapters.mkdocs_site import _ConfigLoader, resolve_site_paths
from egregora.output_adapters.mkdocs_storage import (
    MkDocsEnrichmentStorage,
    MkDocsJournalStorage,
    MkDocsPostStorage,
    MkDocsProfileStorage,
    _write_mkdocs_post,
)

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.storage import EnrichmentStorage, JournalStorage, PostStorage, ProfileStorage

logger = logging.getLogger(__name__)


class MkDocsOutputAdapter(OutputAdapter):
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
        """Initialize MkDocsOutputAdapter with uninitialized storage."""
        self._site_root: Path | None = None
        self._posts_impl: PostStorage | None = None
        self._profiles_impl: ProfileStorage | None = None
        self._journals_impl: JournalStorage | None = None
        self._enrichments_impl: EnrichmentStorage | None = None

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
        self._site_root = site_root

        # Create storage implementations (now defined in this module)
        self._posts_impl = MkDocsPostStorage(site_root, output_format=self)
        self._profiles_impl = MkDocsProfileStorage(site_root)
        self._journals_impl = MkDocsJournalStorage(site_root)
        self._enrichments_impl = MkDocsEnrichmentStorage(site_root)

        logger.debug("Initialized MkDocs storage for %s", site_root)

    @property
    def posts(self) -> PostStorage:
        """Get MkDocs post storage implementation.

        Returns:
            MkDocsPostStorage instance

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._posts_impl is None:
            msg = "MkDocsOutputAdapter not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._posts_impl

    @property
    def profiles(self) -> ProfileStorage:
        """Get MkDocs profile storage implementation.

        Returns:
            MkDocsProfileStorage instance

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._profiles_impl is None:
            msg = "MkDocsOutputAdapter not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._profiles_impl

    @property
    def journals(self) -> JournalStorage:
        """Get MkDocs journal storage implementation.

        Returns:
            MkDocsJournalStorage instance

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._journals_impl is None:
            msg = "MkDocsOutputAdapter not initialized - call initialize(site_root) first"
            raise RuntimeError(msg)
        return self._journals_impl

    @property
    def enrichments(self) -> EnrichmentStorage:
        """Get MkDocs enrichment storage implementation.

        Returns:
            MkDocsEnrichmentStorage instance

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """
        if self._enrichments_impl is None:
            msg = "MkDocsOutputAdapter not initialized - call initialize(site_root) first"
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

        # Check known locations (no upward directory search)
        # 1. Check .egregora/config.yml for custom mkdocs_config_path
        from egregora.output_adapters.mkdocs_site import _try_load_mkdocs_path_from_config

        mkdocs_path_from_config = _try_load_mkdocs_path_from_config(site_root)
        if mkdocs_path_from_config and mkdocs_path_from_config.exists():
            return True

        # 2. Check default location: .egregora/mkdocs.yml
        if (site_root / ".egregora" / "mkdocs.yml").exists():
            return True

        # 3. Check legacy location: root mkdocs.yml
        if (site_root / "mkdocs.yml").exists():
            return True

        return False

    def scaffold_site(self, site_root: Path, site_name: str, **_kwargs: object) -> tuple[Path, bool]:
        """Create the initial MkDocs site structure.

        Creates a comprehensive MkDocs site with:
        - .egregora/mkdocs.yml configuration
        - .egregora/config.yml (Egregora configuration)
        - .egregora/prompts/ (custom prompt overrides)
        - posts/, profiles/, media/ directories
        - index.md, about.md, and other starter pages
        - .gitignore files

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
        site_root.mkdir(parents=True, exist_ok=True)

        # Check if mkdocs.yml already exists ANYWHERE (including custom paths)
        # Prevents duplicate configs - refuse to init if ANY mkdocs.yml exists
        # resolve_site_paths() checks:
        #   1. Custom path from .egregora/config.yml (if configured)
        #   2. .egregora/mkdocs.yml (default new location)
        #   3. mkdocs.yml at root (legacy location)
        site_paths = resolve_site_paths(site_root)

        if site_paths.mkdocs_path and site_paths.mkdocs_path.exists():
            logger.info("MkDocs site already exists at %s (config: %s)", site_root, site_paths.mkdocs_path)
            return (site_paths.mkdocs_path, False)

        # Site doesn't exist - create it
        try:
            # Set up Jinja2 environment for templates
            templates_dir = Path(__file__).resolve().parent.parent / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

            # Render context
            # NOTE: docs_dir is relative to mkdocs.yml location (.egregora/)
            # Since content is in site root, use ".." to point one directory up
            context = {
                "site_name": site_name or site_root.name or "Egregora Archive",
                "blog_dir": "posts",
                "docs_dir": "..",  # Relative to .egregora/mkdocs.yml -> points to site root
                "site_url": "https://example.com",  # Placeholder - update with actual deployment URL
            }

            # Create mkdocs.yml in .egregora/ (default location)
            mkdocs_template = env.get_template("mkdocs.yml.jinja")
            mkdocs_content = mkdocs_template.render(**context)
            new_mkdocs_path = site_paths.mkdocs_config_path  # Default: .egregora/mkdocs.yml
            new_mkdocs_path.parent.mkdir(parents=True, exist_ok=True)
            new_mkdocs_path.write_text(mkdocs_content, encoding="utf-8")
            logger.info("Created .egregora/mkdocs.yml")

            # Create site structure
            self._create_site_structure(site_paths, env, context)
        except Exception as e:
            msg = f"Failed to scaffold MkDocs site: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info("MkDocs site scaffold created at %s", site_root)
            return (new_mkdocs_path, True)

    def _create_site_structure(self, site_paths: Any, env: Any, context: dict[str, Any]) -> None:
        """Create essential directories and index files for the blog structure.

        Args:
            site_paths: SitePaths configuration object
            env: Jinja2 environment for rendering templates
            context: Template rendering context

        """
        # Create .egregora/ structure
        self._create_egregora_structure(site_paths, env)

        # Create content directories
        self._create_content_directories(site_paths)

        # Create template files
        self._create_template_files(site_paths, env, context)

        # Create .egregora/config.yml
        self._create_egregora_config(site_paths, env)

    def _create_content_directories(self, site_paths: Any) -> None:
        """Create main content directories for the site.

        Args:
            site_paths: SitePaths configuration object

        """
        posts_dir = site_paths.posts_dir
        profiles_dir = site_paths.profiles_dir
        media_dir = site_paths.media_dir

        # Create main content directories at root
        for directory in (posts_dir, profiles_dir, media_dir):
            directory.mkdir(parents=True, exist_ok=True)

        # Create media subdirectories with .gitkeep
        for subdir in ["images", "videos", "audio", "documents"]:
            media_subdir = media_dir / subdir
            media_subdir.mkdir(exist_ok=True)
            (media_subdir / ".gitkeep").touch()

        # Create journal directory for agent logs
        journal_dir = posts_dir / "journal"
        journal_dir.mkdir(exist_ok=True)
        (journal_dir / ".gitkeep").touch()

    def _create_template_files(self, site_paths: Any, env: Any, context: dict[str, Any]) -> None:
        """Create starter template files from Jinja2 templates.

        Args:
            site_paths: SitePaths configuration object
            env: Jinja2 environment for rendering templates
            context: Template rendering context

        """
        site_root = site_paths.site_root
        profiles_dir = site_paths.profiles_dir
        media_dir = site_paths.media_dir

        # Define templates to render
        templates_to_render = [
            (site_root / "README.md", "README.md.jinja"),
            (site_root / ".gitignore", ".gitignore.jinja"),
            (site_root / "index.md", "docs/index.md.jinja"),
            (site_root / "about.md", "docs/about.md.jinja"),
            (profiles_dir / "index.md", "docs/profiles/index.md.jinja"),
            (media_dir / "index.md", "docs/media/index.md.jinja"),
        ]

        # Render each template
        for target_path, template_name in templates_to_render:
            if not target_path.exists():
                template = env.get_template(template_name)
                content = template.render(**context)
                target_path.write_text(content, encoding="utf-8")

    def _create_egregora_config(self, site_paths: Any, env: Any) -> None:
        """Create .egregora/config.yml from template.

        Args:
            site_paths: SitePaths configuration object
            env: Jinja2 environment for rendering templates

        """
        config_path = site_paths.config_path
        if not config_path.exists():
            try:
                config_template = env.get_template(".egregora/config.yml.jinja")
                config_content = config_template.render()
                config_path.write_text(config_content, encoding="utf-8")
                logger.info("Created .egregora/config.yml from template")
            except (OSError, TemplateError) as e:
                # Fallback to Pydantic default if template fails
                logger.warning("Failed to render config template: %s. Using Pydantic default.", e)
                create_default_config(site_paths.site_root)

    def _create_egregora_structure(self, site_paths: Any, env: Any | None = None) -> None:
        """Create .egregora/ directory structure with templates.

        Creates:
        - .egregora/config.yml (from template with comments)
        - .egregora/prompts/ (for custom prompt overrides + default copies)
        - .egregora/prompts/system/ (writer system prompts)
        - .egregora/prompts/enrichment/ (URL, media prompts)
        - .egregora/prompts/README.md (usage guide)
        - .egregora/.gitignore (ignore ephemeral data)

        Args:
            site_paths: SitePaths configuration object
            env: Jinja2 environment (optional, will be created if not provided)

        """
        egregora_dir = site_paths.egregora_dir
        egregora_dir.mkdir(parents=True, exist_ok=True)

        # Use template environment if not provided
        if env is None:
            templates_dir = Path(__file__).resolve().parent.parent / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

        # Create prompts directory structure
        prompts_dir = site_paths.prompts_dir
        prompts_dir.mkdir(exist_ok=True)

        # Create subdirectories for prompt categories
        (prompts_dir / "system").mkdir(exist_ok=True)
        (prompts_dir / "enrichment").mkdir(exist_ok=True)

        # Copy default prompts from package to site (version pinning strategy)
        self._copy_default_prompts(prompts_dir)

        # Create prompts README from template
        prompts_readme = prompts_dir / "README.md"
        if not prompts_readme.exists():
            try:
                readme_template = env.get_template(".egregora/prompts/README.md.jinja")
                readme_content = readme_template.render()
                prompts_readme.write_text(readme_content, encoding="utf-8")
                logger.info("Created .egregora/prompts/README.md")
            except (OSError, TemplateError) as e:
                # Fallback to simple README if template fails
                logger.warning("Failed to render prompts README template: %s. Using simple version.", e)
                prompts_readme.write_text(
                    "# Custom Prompts\n\n"
                    "Place custom prompt overrides here with same structure as package defaults.\n\n"
                    "See https://docs.egregora.ai for more information.\n",
                    encoding="utf-8",
                )

        # Create .gitignore
        gitignore = egregora_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "# Ephemeral data (regenerated on each run)\n"
                ".cache/\n"
                "rag/*.duckdb\n"
                "rag/*.parquet\n"
                "rag/*.duckdb.wal\n"
                "\n"
                "# Python cache\n"
                "__pycache__/\n"
                "*.pyc\n",
                encoding="utf-8",
            )
            logger.info("Created .egregora/.gitignore")

    def _copy_default_prompts(self, target_prompts_dir: Path) -> None:
        """Copy default prompt templates from package to site.

        This implements the "version pinning" strategy: prompts are copied once during
        init and become site-specific. Users can customize without losing changes,
        and Egregora can update defaults without breaking existing sites.

        Args:
            target_prompts_dir: Destination directory (.egregora/prompts/)

        """
        # Find source prompts directory in package
        package_prompts_dir = Path(__file__).resolve().parent.parent / "prompts"

        if not package_prompts_dir.exists():
            logger.warning("Package prompts directory not found: %s", package_prompts_dir)
            return

        # Copy all .jinja files from package to site
        prompt_files_copied = 0
        for source_file in package_prompts_dir.rglob("*.jinja"):
            # Compute relative path to preserve directory structure
            rel_path = source_file.relative_to(package_prompts_dir)
            target_file = target_prompts_dir / rel_path

            # Only copy if target doesn't exist (don't overwrite customizations)
            if not target_file.exists():
                target_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target_file.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")
                    prompt_files_copied += 1
                except (OSError, UnicodeDecodeError) as e:
                    logger.warning("Failed to copy prompt %s: %s", source_file.name, e)

        if prompt_files_copied > 0:
            logger.info("Copied %d default prompt templates to %s", prompt_files_copied, target_prompts_dir)

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
        # Load mkdocs.yml to get site_name (already resolved by resolve_site_paths)
        if site_paths.mkdocs_path:
            try:
                mkdocs_config = (
                    yaml.load(site_paths.mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}
                )
            except yaml.YAMLError as exc:
                logger.warning("Failed to parse mkdocs.yml at %s: %s", site_paths.mkdocs_path, exc)
                mkdocs_config = {}
        else:
            logger.debug("mkdocs.yml not found in %s", site_root)
            mkdocs_config = {}
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
            return _write_mkdocs_post(content, metadata, output_dir)
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
        # Use resolve_site_paths to find mkdocs.yml (checks custom path, .egregora/, root)
        site_paths = resolve_site_paths(site_root)
        if not site_paths.mkdocs_path:
            msg = f"No mkdocs.yml found in {site_root}"
            raise FileNotFoundError(msg)
        try:
            config = yaml.load(site_paths.mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse mkdocs.yml at %s: %s", site_paths.mkdocs_path, exc)
            config = {}
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

    def list_documents(self) -> Table:
        """List all MkDocs documents (posts, profiles, media enrichments) as Ibis table.

        Returns Ibis table with storage identifiers (relative paths) and modification times.
        This enables efficient delta detection using Ibis joins/filters.

        Returns:
            Ibis table with schema:
                - storage_identifier: string (relative path from site_root)
                - mtime_ns: int64 (modification time in nanoseconds)

        Example identifiers:
            - Posts: "posts/2025-01-10-my-post.md"
            - Profiles: "profiles/user-123.md"
            - Media enrichments: "docs/media/images/uuid.png.md"
            - URL enrichments: "media/urls/uuid.md"

        """
        if not hasattr(self, "_site_root") or self._site_root is None:
            # Return empty table with correct schema
            return ibis.memtable(
                [], schema=ibis.schema({"storage_identifier": "string", "mtime_ns": "int64"})
            )

        documents = []

        # Scan posts directory
        posts_dir = self._site_root / "posts"
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
        profiles_dir = self._site_root / "profiles"
        if profiles_dir.exists():
            for profile_file in profiles_dir.glob("*.md"):
                if profile_file.is_file():
                    try:
                        relative_path = str(profile_file.relative_to(self._site_root))
                        mtime_ns = profile_file.stat().st_mtime_ns
                        documents.append({"storage_identifier": relative_path, "mtime_ns": mtime_ns})
                    except (OSError, ValueError):
                        continue

        # Scan media enrichments (docs/media/**/*.md, excluding index.md)
        docs_media_dir = self._site_root / "docs" / "media"
        if docs_media_dir.exists():
            for enrichment_file in docs_media_dir.rglob("*.md"):
                if enrichment_file.is_file() and enrichment_file.name != "index.md":
                    try:
                        relative_path = str(enrichment_file.relative_to(self._site_root))
                        mtime_ns = enrichment_file.stat().st_mtime_ns
                        documents.append({"storage_identifier": relative_path, "mtime_ns": mtime_ns})
                    except (OSError, ValueError):
                        continue

        # Scan URL enrichments (media/urls/**/*.md)
        # Published via mkdocs.yml configuration (docs_dir: '.' or navigation)
        media_dir = self._site_root / "media"
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
