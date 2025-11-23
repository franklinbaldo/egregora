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
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape

from egregora.config.settings import EgregoraConfig, create_default_config
from egregora.data_primitives import DocumentMetadata
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlContext, UrlConvention
from egregora.knowledge.profiles import write_profile as write_profile_content
from egregora.output_adapters.base import OutputAdapter, SiteConfiguration
from egregora.output_adapters.conventions import StandardUrlConvention
from egregora.output_adapters.mkdocs.paths import compute_site_prefix, derive_mkdocs_paths
from egregora.utils.filesystem import (
    _ensure_author_entries,
    _format_frontmatter_datetime,
)
from egregora.utils.filesystem import (
    write_markdown_post as _write_mkdocs_post,
)
from egregora.utils.frontmatter_utils import parse_frontmatter
from egregora.utils.paths import slugify

logger = logging.getLogger(__name__)


# Custom YAML loader that ignores unknown tags
class _ConfigLoader(yaml.SafeLoader):
    """YAML loader that ignores unknown tags (like !ENV)."""


_ConfigLoader.add_constructor(None, lambda loader, node: None)


class MkDocsAdapter(OutputAdapter):
    """Unified MkDocs output adapter.

    **ISP-COMPLIANT** (2025-11-22): This adapter implements both:
    - OutputSink: Runtime data operations (persist, read, list documents)
    - SiteScaffolder: Project lifecycle operations (scaffold_site, supports_site, resolve_paths)

    This dual implementation makes MkDocsAdapter suitable for:
    1. Pipeline execution (via OutputSink interface)
    2. Site initialization (via SiteScaffolder interface)

    For adapters that only need data persistence (e.g., PostgresAdapter, S3Adapter),
    implement only OutputSink. For pure initialization tools, implement only SiteScaffolder.
    """

    def __init__(self) -> None:
        """Initializes the adapter."""
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

    def get_media_url_path(self, media_file: Path, site_root: Path) -> str:
        """Get the relative URL path for a media file in the generated site.

        Args:
            media_file: Absolute path to the media file
            site_root: Root directory of the site

        Returns:
            Relative path string for use in HTML/markdown links
            Example: "media/images/abc123.jpg"

        """
        site_config = self.resolve_paths(site_root)
        return str(media_file.relative_to(site_config.docs_dir))

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

        # Phase 2: Add author cards to POST documents
        if document.type == DocumentType.POST and document.metadata:
            authors = document.metadata.get("authors", [])
            if authors and isinstance(authors, list):
                # Append author cards using Jinja template
                document.content = self._append_author_cards(document.content, authors)

        self._write_document(document, path)
        self._index[doc_id] = path
        logger.debug("Served document %s at %s", doc_id, path)

    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:  # noqa: C901
        if isinstance(doc_type, str):
            doc_type = DocumentType(doc_type)
        path: Path | None = None

        if doc_type == DocumentType.PROFILE:
            path = self.profiles_dir / f"{identifier}.md"
        elif doc_type == DocumentType.POST:
            matches = list(self.posts_dir.glob(f"*-{identifier}.md"))
            if matches:
                path = max(matches, key=lambda p: p.stat().st_mtime)
        elif doc_type == DocumentType.JOURNAL:
            safe_identifier = identifier.replace("/", "-")
            path = self.journal_dir / f"{safe_identifier}.md"
        elif doc_type == DocumentType.ENRICHMENT_URL:
            path = self.urls_dir / f"{identifier}.md"
        elif doc_type == DocumentType.ENRICHMENT_MEDIA:
            path = self.media_dir / f"{identifier}.md"
        elif doc_type == DocumentType.MEDIA:
            path = self.media_dir / identifier

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
        """Check if the site root contains a mkdocs.yml file.

        READ-ONLY: Does not create any files or directories.

        Args:
            site_root: Path to check

        Returns:
            True if mkdocs.yml exists in site_root or standard locations

        """
        if not site_root.exists():
            return False

        # Check .egregora/mkdocs.yml (modern location)
        egregora_mkdocs = site_root / ".egregora" / "mkdocs.yml"
        if egregora_mkdocs.exists():
            return True

        # Check root mkdocs.yml (legacy location)
        legacy_path = site_root / "mkdocs.yml"
        return legacy_path.exists()

    def scaffold_site(self, site_root: Path, site_name: str, **_kwargs: object) -> tuple[Path, bool]:
        """Create the initial MkDocs site structure.

        Creates a comprehensive MkDocs site with:
        - .egregora/mkdocs.yml configuration
        - .egregora/config.yml (Egregora configuration)
        - .egregora/prompts/ (custom prompt overrides)
        - .github/workflows/publish.yml (GitHub Actions deployment)
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
        # derive_mkdocs_paths() checks:
        #   1. .egregora/mkdocs.yml (default new location)
        #   2. mkdocs.yml at root (legacy location)
        site_paths = derive_mkdocs_paths(site_root)

        mkdocs_path = site_paths.get("mkdocs_path")
        site_exists = False
        if mkdocs_path and mkdocs_path.exists():
            logger.info("MkDocs site already exists at %s (config: %s)", site_root, mkdocs_path)
            site_exists = True

        legacy_mkdocs = site_root / "mkdocs.yml"
        if legacy_mkdocs.exists() and legacy_mkdocs != mkdocs_path:
            logger.info("MkDocs site already exists at %s (config: %s)", site_root, legacy_mkdocs)
            site_exists = True

        # Site doesn't exist - create it
        try:
            # Set up Jinja2 environment for templates
            templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

            # Render context (paths relative to mkdocs.yml inside .egregora/)
            mkdocs_config_dir = site_paths["mkdocs_config_path"].parent
            docs_dir = site_paths["docs_dir"]
            docs_relative = Path(os.path.relpath(docs_dir, mkdocs_config_dir)).as_posix()
            blog_relative = Path(os.path.relpath(site_paths["posts_dir"], docs_dir)).as_posix()

            context = {
                "site_name": site_name or site_root.name or "Egregora Archive",
                "site_root": site_root,
                "blog_dir": blog_relative,
                "docs_dir": docs_relative,
                "site_url": "https://example.com",  # Placeholder - update with actual deployment URL
                "generated_date": datetime.now(UTC).strftime("%Y-%m-%d"),
                "default_writer_model": EgregoraConfig().models.writer,
            }

            # Create mkdocs.yml in .egregora/ (default location) ONLY if it doesn't exist
            new_mkdocs_path = site_paths["mkdocs_config_path"]  # Default: .egregora/mkdocs.yml
            if not site_exists:
                mkdocs_template = env.get_template("mkdocs.yml.jinja")
                mkdocs_content = mkdocs_template.render(**context)
                new_mkdocs_path.parent.mkdir(parents=True, exist_ok=True)
                new_mkdocs_path.write_text(mkdocs_content, encoding="utf-8")
                logger.info("Created .egregora/mkdocs.yml")
            else:
                # Use existing path for return value
                new_mkdocs_path = mkdocs_path or legacy_mkdocs

            # Create site structure (will only create missing files)
            self._create_site_structure(site_paths, env, context)
        except Exception as e:
            msg = f"Failed to scaffold MkDocs site: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info("MkDocs site scaffold checked/updated at %s", site_root)
            return (new_mkdocs_path, not site_exists)

    # SiteScaffolder protocol -------------------------------------------------

    def scaffold(self, path: Path, config: dict) -> None:
        site_name = config.get("site_name") if isinstance(config, dict) else None
        mkdocs_path, created = self.scaffold_site(path, site_name or path.name)
        if not created:
            logger.info("MkDocs site already exists at %s (config: %s)", path, mkdocs_path)

    def _create_site_structure(
        self, site_paths: dict[str, Any], env: Environment, context: dict[str, Any]
    ) -> None:
        """Create essential directories and index files for the blog structure.

        Args:
            site_paths: Dictionary of site paths
            env: Jinja2 environment for rendering templates
            context: Template rendering context

        """
        if not isinstance(site_paths, dict):
            msg = "site_paths must be a dict"
            raise TypeError(msg)
        if not isinstance(env, Environment):
            msg = "env must be a Jinja2 Environment"
            raise TypeError(msg)

        # Create .egregora/ structure
        self._create_egregora_structure(site_paths, env)

        # Create content directories
        self._create_content_directories(site_paths)

        # Create template files
        self._create_template_files(site_paths, env, context)

        # Create .egregora/config.yml
        self._create_egregora_config(site_paths, env)

    def _create_content_directories(self, site_paths: dict[str, Any]) -> None:
        """Create main content directories for the site.

        Args:
            site_paths: Dictionary of site paths

        """
        if not isinstance(site_paths, dict):
            msg = "site_paths must be a dict"
            raise TypeError(msg)

        posts_dir = site_paths["posts_dir"]
        profiles_dir = site_paths["profiles_dir"]
        media_dir = site_paths["media_dir"]
        journal_dir = site_paths["journal_dir"]

        # Create main content directories at root
        for directory in (posts_dir, profiles_dir, media_dir, journal_dir):
            directory.mkdir(parents=True, exist_ok=True)

        # Create media subdirectories with .gitkeep
        for subdir in ["images", "videos", "audio", "documents"]:
            media_subdir = media_dir / subdir
            media_subdir.mkdir(exist_ok=True)
            (media_subdir / ".gitkeep").touch()

        # Ensure journal dir has gitkeep
        journal_dir.mkdir(exist_ok=True)
        (journal_dir / ".gitkeep").touch()

    def _create_template_files(
        self, site_paths: dict[str, Any], env: Environment, context: dict[str, Any]
    ) -> None:
        """Create starter template files from Jinja2 templates.

        Args:
            site_paths: Dictionary of site paths
            env: Jinja2 environment for rendering templates
            context: Template rendering context

        """
        if not isinstance(site_paths, dict):
            msg = "site_paths must be a dict"
            raise TypeError(msg)
        if not isinstance(env, Environment):
            msg = "env must be a Jinja2 Environment"
            raise TypeError(msg)

        site_root = site_paths["site_root"]
        docs_dir = site_paths["docs_dir"]
        profiles_dir = site_paths["profiles_dir"]
        media_dir = site_paths["media_dir"]
        posts_dir = site_paths["posts_dir"]

        # Define templates to render
        templates_to_render = [
            (site_root / "README.md", "README.md.jinja"),
            (site_root / ".gitignore", ".gitignore.jinja"),
            (site_root / ".github" / "workflows" / "publish.yml", ".github/workflows/publish.yml.jinja"),
            (docs_dir / "index.md", "docs/index.md.jinja"),
            (docs_dir / "about.md", "docs/about.md.jinja"),
            (docs_dir / "journal" / "index.md", "docs/journal/index.md.jinja"),
            (profiles_dir / "index.md", "docs/profiles/index.md.jinja"),
            (media_dir / "index.md", "docs/media/index.md.jinja"),
            (posts_dir / "index.md", "docs/posts/index.md.jinja"),
            (posts_dir / "tags.md", "docs/posts/tags.md.jinja"),
        ]

        # Add custom CSS (not a Jinja template, just copy)
        stylesheets_dir = docs_dir / "stylesheets"
        stylesheets_dir.mkdir(parents=True, exist_ok=True)
        custom_css_src = Path(env.loader.searchpath[0]) / "docs" / "stylesheets" / "custom.css"
        custom_css_dest = stylesheets_dir / "custom.css"
        if custom_css_src.exists() and not custom_css_dest.exists():
            import shutil

            shutil.copy(custom_css_src, custom_css_dest)

        # Render each template
        for target_path, template_name in templates_to_render:
            if not target_path.exists():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                template = env.get_template(template_name)
                content = template.render(**context)
                target_path.write_text(content, encoding="utf-8")

    def _create_egregora_config(self, site_paths: dict[str, Any], env: Environment) -> None:
        """Create .egregora/config.yml from template.

        Args:
            site_paths: Dictionary of site paths
            env: Jinja2 environment for rendering templates

        """
        if not isinstance(site_paths, dict):
            msg = "site_paths must be a dict"
            raise TypeError(msg)
        if not isinstance(env, Environment):
            msg = "env must be a Jinja2 Environment"
            raise TypeError(msg)

        config_path = site_paths["config_path"]
        if not config_path.exists():
            try:
                config_template = env.get_template(".egregora/config.yml.jinja")
                config_content = config_template.render()
                config_path.write_text(config_content, encoding="utf-8")
                logger.info("Created .egregora/config.yml from template")
            except (OSError, TemplateError) as e:
                # Fallback to Pydantic default if template fails
                logger.warning("Failed to render config template: %s. Using Pydantic default.", e)
                create_default_config(site_paths["site_root"])

    def _create_egregora_structure(self, site_paths: dict[str, Any], env: Any | None = None) -> None:
        """Create .egregora/ directory structure with templates.

        Creates:
        - .egregora/config.yml (from template with comments)
        - .egregora/prompts/ (flat directory for prompt overrides)
        - .egregora/prompts/README.md (usage guide)
        - .egregora/.gitignore (ignore ephemeral data)

        Args:
            site_paths: Dictionary of site paths
            env: Jinja2 environment (optional, will be created if not provided)

        """
        from egregora.resources.prompts import PromptManager

        egregora_dir = site_paths["egregora_dir"]
        egregora_dir.mkdir(parents=True, exist_ok=True)

        # Use template environment if not provided
        if env is None:
            templates_dir = Path(__file__).resolve().parent.parent / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

        # Create prompts directory
        prompts_dir = site_paths["prompts_dir"]
        prompts_dir.mkdir(exist_ok=True)

        # Copy default prompts from package to site using centralized manager
        PromptManager.copy_defaults(prompts_dir)

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
            site_paths = derive_mkdocs_paths(site_root)
        except Exception as e:
            msg = f"Failed to resolve site paths: {e}"
            raise RuntimeError(msg) from e
        config_file = site_paths.get("mkdocs_path")
        # Load mkdocs.yml to get site_name
        mkdocs_path = site_paths.get("mkdocs_path")
        if mkdocs_path:
            try:
                mkdocs_config = (
                    yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}  # noqa: S506
                )
            except yaml.YAMLError as exc:
                logger.warning("Failed to parse mkdocs.yml at %s: %s", mkdocs_path, exc)
                mkdocs_config = {}
        else:
            logger.debug("mkdocs.yml not found in %s", site_root)
            mkdocs_config = {}
        return SiteConfiguration(
            site_root=site_paths["site_root"],
            site_name=mkdocs_config.get("site_name", "Egregora Site"),
            docs_dir=site_paths["docs_dir"],
            posts_dir=site_paths["posts_dir"],
            profiles_dir=site_paths["profiles_dir"],
            media_dir=site_paths["media_dir"],
            config_file=config_file,
            additional_paths={
                "rag_dir": site_paths["rag_dir"],
                "enriched_dir": site_paths["enriched_dir"],
                "rankings_dir": site_paths["rankings_dir"],
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
        # Use derive_mkdocs_paths to find mkdocs.yml (checks .egregora/, root)
        site_paths = derive_mkdocs_paths(site_root)
        mkdocs_path = site_paths.get("mkdocs_path")
        if not mkdocs_path:
            msg = f"No mkdocs.yml found in {site_root}"
            raise FileNotFoundError(msg)
        try:
            config = yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}  # noqa: S506
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse mkdocs.yml at %s: %s", mkdocs_path, exc)
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

Tags automatically create taxonomy pages where readers can browse posts by topic.
Use consistent, meaningful tags across posts to build a useful taxonomy.
"""

    def documents(self) -> Iterator[Document]:
        """Return all MkDocs documents as Document instances (lazy iterator)."""
        if not hasattr(self, "_site_root") or self._site_root is None:
            return

        yield from self._documents_from_dir(self.posts_dir, DocumentType.POST)
        yield from self._documents_from_dir(self.profiles_dir, DocumentType.PROFILE)
        yield from self._documents_from_dir(
            self._site_root / "docs" / "media",
            DocumentType.ENRICHMENT_MEDIA,
            recursive=True,
            exclude_names={"index.md"},
        )
        yield from self._documents_from_dir(
            self.media_dir / "urls", DocumentType.ENRICHMENT_URL, recursive=True
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

    def _url_to_path(self, url: str, document: Document) -> Path:  # noqa: PLR0911, C901
        base = self._ctx.base_url.rstrip("/")
        if url.startswith(base):
            url_path = url[len(base) :]
        else:
            url_path = url

        url_path = url_path.strip("/")

        if document.type == DocumentType.POST:
            return self.posts_dir / f"{url_path.split('/')[-1]}.md"
        if document.type == DocumentType.PROFILE:
            return self.profiles_dir / f"{url_path.split('/')[-1]}.md"
        if document.type == DocumentType.JOURNAL:
            return self.journal_dir / f"{url_path.split('/')[-1]}.md"
        if document.type == DocumentType.ENRICHMENT_URL:
            # url_path might be 'media/urls/slug' -> we want 'slug.md' inside urls_dir
            slug = url_path.split("/")[-1]
            return self.urls_dir / f"{slug}.md"
        if document.type == DocumentType.ENRICHMENT_MEDIA:
            # url_path might be 'media/images/slug' -> we want 'slug.md' inside media/images
            # We need to preserve the subdirectory (images/videos/etc)
            # url_path is like 'media/images/foo'
            # self.media_dir is 'docs/media'
            # We want 'docs/media/images/foo.md'

            # Strip the prefix (media/) from url_path if present
            rel_path = url_path
            media_prefix = self._ctx.site_prefix + "/media" if self._ctx.site_prefix else "media"
            if rel_path.startswith(media_prefix):
                rel_path = rel_path[len(media_prefix) :].strip("/")
            elif rel_path.startswith("media/"):
                rel_path = rel_path[6:]

            return self.media_dir / f"{rel_path}.md"

        if document.type == DocumentType.MEDIA:
            # Similar logic for media files
            rel_path = url_path
            media_prefix = self._ctx.site_prefix + "/media" if self._ctx.site_prefix else "media"
            if rel_path.startswith(media_prefix):
                rel_path = rel_path[len(media_prefix) :].strip("/")
            elif rel_path.startswith("media/"):
                rel_path = rel_path[6:]
            return self.media_dir / rel_path

        return self.site_root / f"{url_path}.md"

    def _write_document(self, document: Document, path: Path) -> None:  # noqa: C901
        import yaml as _yaml

        path.parent.mkdir(parents=True, exist_ok=True)

        def _ensure_hidden(metadata: dict[str, Any]) -> dict[str, Any]:
            hide = metadata.get("hide", [])
            if isinstance(hide, str):
                hide = [hide]
            if "navigation" not in hide:
                hide.append("navigation")
            metadata["hide"] = hide
            metadata["nav_exclude"] = metadata.get("nav_exclude", True)
            return metadata

        if document.type == DocumentType.POST:
            metadata = dict(document.metadata or {})
            if "date" in metadata:
                metadata["date"] = _format_frontmatter_datetime(metadata["date"])
            if "authors" in metadata:
                _ensure_author_entries(path.parent, metadata.get("authors"))

            yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
            full_content = f"---\n{yaml_front}---\n\n{document.content}"
            path.write_text(full_content, encoding="utf-8")
        elif document.type == DocumentType.JOURNAL:
            metadata = _ensure_hidden(dict(document.metadata or {}))
            yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
            full_content = f"---\n{yaml_front}---\n\n{document.content}"
            path.write_text(full_content, encoding="utf-8")
        elif document.type == DocumentType.PROFILE:
            from egregora.knowledge.profiles import (
                write_profile as write_profile_content,
            )

            author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
            if not author_uuid:
                msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
                raise ValueError(msg)
            write_profile_content(author_uuid, document.content, self.profiles_dir)
        elif document.type in (DocumentType.ENRICHMENT_URL, DocumentType.ENRICHMENT_MEDIA):
            metadata = _ensure_hidden(document.metadata.copy())
            metadata.setdefault("document_type", document.type.value)
            metadata.setdefault("slug", document.slug)
            if document.parent_id:
                metadata.setdefault("parent_id", document.parent_id)
            if document.parent and document.parent.metadata.get("slug"):
                metadata.setdefault("parent_slug", document.parent.metadata.get("slug"))

            yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
            full_content = f"---\n{yaml_front}---\n\n{document.content}"
            path.write_text(full_content, encoding="utf-8")
        elif document.type == DocumentType.MEDIA:
            payload = (
                document.content if isinstance(document.content, bytes) else document.content.encode("utf-8")
            )
            path.write_bytes(payload)
        elif isinstance(document.content, bytes):
            path.write_bytes(document.content)
        else:
            path.write_text(document.content, encoding="utf-8")

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

    def _get_site_stats(self) -> dict[str, int]:
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

    def _get_profiles_data(self) -> list[dict[str, Any]]:
        """Extract profile metadata for profiles index.

        Returns:
            List of profile dictionaries with uuid, name, avatar, bio, topics

        """
        profiles = []

        if not hasattr(self, "profiles_dir") or not self.profiles_dir.exists():
            return profiles

        for profile_path in sorted(self.profiles_dir.glob("[!index]*.md")):
            try:
                content = profile_path.read_text(encoding="utf-8")
                metadata, _ = parse_frontmatter(content)

                # Use avatar from frontmatter or generate fallback
                avatar = metadata.get("avatar", "")
                if not avatar:
                    from egregora.knowledge.profiles import _generate_fallback_avatar_url

                    avatar = _generate_fallback_avatar_url(profile_path.stem)

                profiles.append(
                    {
                        "uuid": profile_path.stem,
                        "name": metadata.get("name", profile_path.stem[:8]),
                        "avatar": avatar,
                        "bio": metadata.get("bio", "Profile pending - first contributions detected"),
                        "topics": metadata.get("topics", []),
                    }
                )
            except (OSError, yaml.YAMLError) as e:
                logger.warning("Failed to parse profile %s: %s", profile_path, e)
                continue

        return profiles

    def _get_recent_media(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recent media items for media index.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of media dictionaries with title, url, slug, summary

        """
        media_items = []

        urls_dir = self.media_dir / "urls" if hasattr(self, "media_dir") else None
        if not urls_dir or not urls_dir.exists():
            return media_items

        # Get all URL enrichments, sorted by modification time (newest first)
        url_files = sorted(urls_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

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
            for potential_path in [self.site_root / "docs" / ".authors.yml", self.site_root / ".authors.yml"]:
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

            if not avatar:
                from egregora.knowledge.profiles import _generate_fallback_avatar_url

                avatar = _generate_fallback_avatar_url(author_id)

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
