"""MkDocs output adapters and filesystem helpers.

This module consolidates all MkDocs-specific logic that used to live across
``mkdocs.py``, ``mkdocs_output_adapter.py``, ``mkdocs_site.py`` and
``mkdocs_storage.py``.  It exposes both the legacy registry-friendly
``MkDocsOutputAdapter`` as well as the modern document-centric
``MkDocsFilesystemAdapter`` alongside shared helpers for resolving site
configuration and working with MkDocs' filesystem layout.

MODERN (2025-11-18): Imports site path resolution from config.site to eliminate duplication.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from dateutil import parser as dateutil_parser
from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape


# Custom YAML loader that ignores unknown tags
class _ConfigLoader(yaml.SafeLoader):
    """YAML loader that ignores unknown tags (like !ENV)."""


_ConfigLoader.add_constructor(None, lambda loader, node: None)

from egregora.agents.shared.author_profiles import write_profile as write_profile_content
from egregora.config.settings import create_default_config
from egregora.config.site import (
    SitePaths,
    resolve_site_paths,
)
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlContext, UrlConvention
from egregora.output_adapters.base import OutputAdapter, SiteConfiguration
from egregora.utils.frontmatter_utils import parse_frontmatter
from egregora.utils.paths import safe_path_join, slugify

if TYPE_CHECKING:
    from ibis.expr.types import Table


logger = logging.getLogger(__name__)


class MkDocsUrlConvention:
    """Canonical URL convention for MkDocs sites.

    This is the ONE and ONLY URL scheme for Egregora MkDocs output.

    URL patterns:
    - Posts: /posts/{YYYY-MM-DD}-{slug}/
    - Profiles: /profiles/{uuid}/
    - Journals: /posts/journal/journal_{window_label}/
    - URL enrichments: /docs/media/urls/{doc_id}/
    - Media enrichments: /docs/media/{filename}
    - Media files: /docs/media/{filename}
    """

    @property
    def name(self) -> str:
        """Convention identifier."""
        return "mkdocs-v1"

    @property
    def version(self) -> str:
        """Convention version."""
        return "1.0.0"

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Generate canonical URL for a document.

        Args:
            document: Document to generate URL for
            ctx: URL context with base_url

        Returns:
            Canonical URL string

        """
        base = ctx.base_url.rstrip("/")

        if document.type == DocumentType.POST:
            slug = document.metadata.get("slug", document.document_id[:8])
            date_val = document.metadata.get("date", "")
            normalized_slug = slugify(slug)

            if date_val:
                # Handle datetime objects or strings
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)
                return f"{base}/posts/{date_str}-{normalized_slug}/"
            return f"{base}/posts/{normalized_slug}/"

        if document.type == DocumentType.PROFILE:
            author_uuid = document.metadata.get("uuid") or document.metadata.get("author_uuid")
            if not author_uuid:
                msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
                raise ValueError(msg)
            return f"{base}/profiles/{author_uuid}/"

        if document.type == DocumentType.JOURNAL:
            window_label = document.metadata.get("window_label", document.source_window or "unlabeled")
            safe_label = window_label.replace(" ", "_").replace(":", "-")
            return f"{base}/posts/journal/journal_{safe_label}/"

        if document.type == DocumentType.ENRICHMENT_URL:
            return f"{base}/docs/media/urls/{document.document_id}/"

        if document.type == DocumentType.ENRICHMENT_MEDIA:
            filename = document.suggested_path or f"{document.document_id}.md"
            filename = filename.removeprefix("docs/media/")
            return f"{base}/docs/media/{filename}"

        if document.type == DocumentType.MEDIA:
            filename = document.suggested_path or document.document_id
            filename = filename.removeprefix("docs/media/")
            return f"{base}/docs/media/{filename}"

        # Fallback for unknown types
        return f"{base}/documents/{document.document_id}/"


class MkDocsAdapter(OutputAdapter):
    """Unified MkDocs output adapter."""

    def __init__(self) -> None:
        """Initializes the adapter."""
        self._initialized = False
        self.site_root = None
        self._url_convention = MkDocsUrlConvention()
        self._index: dict[str, Path] = {}
        self._ctx: UrlContext | None = None

    def initialize(self, site_root: Path, url_context: UrlContext | None = None) -> None:
        """Initializes the adapter with all necessary paths and dependencies."""
        self.site_root = site_root
        self._ctx = url_context or UrlContext(base_url="")
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
        self._initialized = True

    @property
    def posts(self):
        return self

    @property
    def profiles(self):
        return self

    @property
    def journals(self):
        return self

    @property
    def enrichments(self):
        return self

    @property
    def format_type(self) -> str:
        """Return 'mkdocs' as the format type identifier."""
        return "mkdocs"

    @property
    def url_convention(self) -> UrlConvention:
        return self._url_convention

    def serve(self, document: Document) -> None:
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

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
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
            safe_label = identifier.replace(" ", "_").replace(":", "-")
            path = self.journal_dir / f"journal_{safe_label}.md"
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
                content = raw_bytes.decode("utf-8", errors="ignore")
                metadata: dict[str, Any] = {"filename": path.name}
                actual_content = content
            else:
                content = path.read_text(encoding="utf-8")
                metadata, actual_content = parse_frontmatter(content)
        except OSError:
            logger.exception("Failed to read document at %s", path)
            return None

        return Document(content=actual_content, type=doc_type, metadata=metadata)

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file.

        Args:
            site_root: Path to check

        Returns:
            True if mkdocs.yml exists in site_root or standard locations

        """
        if not site_root.exists():
            return False

        # Check known locations (no upward directory search)
        # Uses resolve_site_paths which checks:
        #   1. Custom path from .egregora/config.yml (if configured)
        #   2. .egregora/mkdocs.yml (default new location)
        #   3. mkdocs.yml at root (legacy location)
        try:
            site_paths = resolve_site_paths(site_root)
            return site_paths.mkdocs_path is not None and site_paths.mkdocs_path.exists()
        except Exception:
            # If resolve fails, fall back to simple checks
            return (site_root / ".egregora" / "mkdocs.yml").exists() or (site_root / "mkdocs.yml").exists()

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
            templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
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

    def _create_site_structure(
        self, site_paths: SitePaths, env: Environment, context: dict[str, Any]
    ) -> None:
        """Create essential directories and index files for the blog structure.

        Args:
            site_paths: SitePaths configuration object
            env: Jinja2 environment for rendering templates
            context: Template rendering context

        """
        assert isinstance(site_paths, SitePaths), "site_paths must be a SitePaths instance"
        assert isinstance(env, Environment), "env must be a Jinja2 Environment"

        # Create .egregora/ structure
        self._create_egregora_structure(site_paths, env)

        # Create content directories
        self._create_content_directories(site_paths)

        # Create template files
        self._create_template_files(site_paths, env, context)

        # Create .egregora/config.yml
        self._create_egregora_config(site_paths, env)

    def _create_content_directories(self, site_paths: SitePaths) -> None:
        """Create main content directories for the site.

        Args:
            site_paths: SitePaths configuration object

        """
        assert isinstance(site_paths, SitePaths), "site_paths must be a SitePaths instance"

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

    def _create_template_files(
        self, site_paths: SitePaths, env: Environment, context: dict[str, Any]
    ) -> None:
        """Create starter template files from Jinja2 templates.

        Args:
            site_paths: SitePaths configuration object
            env: Jinja2 environment for rendering templates
            context: Template rendering context

        """
        assert isinstance(site_paths, SitePaths), "site_paths must be a SitePaths instance"
        assert isinstance(env, Environment), "env must be a Jinja2 Environment"

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

    def _create_egregora_config(self, site_paths: SitePaths, env: Environment) -> None:
        """Create .egregora/config.yml from template.

        Args:
            site_paths: SitePaths configuration object
            env: Jinja2 environment for rendering templates

        """
        assert isinstance(site_paths, SitePaths), "site_paths must be a SitePaths instance"
        assert isinstance(env, Environment), "env must be a Jinja2 Environment"

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

        REFACTORED (2025-11-19): Now uses base class helper _scan_directory_for_documents()
        to reduce code duplication with other output adapters.

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
            return self._empty_document_table()

        site_root = self._site_root
        documents: list[dict] = []

        # Scan posts directory
        documents.extend(self._scan_directory_for_documents(site_root / "posts", site_root, "*.md"))

        # Scan profiles directory
        documents.extend(self._scan_directory_for_documents(site_root / "profiles", site_root, "*.md"))

        # Scan media enrichments (docs/media/**/*.md, excluding index.md)
        documents.extend(
            self._scan_directory_for_documents(
                site_root / "docs" / "media",
                site_root,
                "*.md",
                recursive=True,
                exclude_names={"index.md"},
            )
        )

        # Scan URL enrichments (media/urls/**/*.md)
        documents.extend(
            self._scan_directory_for_documents(site_root / "media", site_root, "*.md", recursive=True)
        )

        return self._documents_to_table(documents)

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

    @property
    def url_convention(self) -> UrlConvention:
        return self._url_convention

    def serve(self, document: Document) -> None:
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

    def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
        path: Path | None = None

        if doc_type == DocumentType.PROFILE:
            path = self.profiles_dir / f"{identifier}.md"
        elif doc_type == DocumentType.POST:
            matches = list(self.posts_dir.glob(f"*-{identifier}.md"))
            if matches:
                path = max(matches, key=lambda p: p.stat().st_mtime)
        elif doc_type == DocumentType.JOURNAL:
            safe_label = identifier.replace(" ", "_").replace(":", "-")
            path = self.journal_dir / f"journal_{safe_label}.md"
        elif doc_type == DocumentType.ENRICHMENT_URL:
            path = self.urls_dir / f"{identifier}.md"
        elif doc_type == DocumentType.ENRICHMENT_MEDIA:
            path = self.media_dir / f"{identifier}.md"
        elif doc_type == DocumentType.MEDIA:
            path = self.media_dir / identifier

        if path is None or not path.exists():
            logger.debug("Document not found: %s/%s", doc_type.value, identifier)
            return None

        try:
            if doc_type == DocumentType.MEDIA:
                raw_bytes = path.read_bytes()
                content = raw_bytes.decode("utf-8", errors="ignore")
                metadata: dict[str, Any] = {"filename": path.name}
                actual_content = content
            else:
                content = path.read_text(encoding="utf-8")
                metadata, actual_content = parse_frontmatter(content)
        except OSError:
            logger.exception("Failed to read document at %s", path)
            return None

        return Document(content=actual_content, type=doc_type, metadata=metadata)

    def list_documents(self, doc_type: DocumentType | None = None) -> list[Document]:
        documents: list[Document] = []

        def read_dir(directory: Path, dtype: DocumentType, pattern: str = "*.md") -> None:
            if not directory.exists():
                return
            for file_path in directory.glob(pattern):
                identifier = file_path.stem
                if dtype == DocumentType.POST:
                    parts = identifier.split("-", 3)
                    if len(parts) >= 4:
                        identifier = parts[3]
                doc = self.read_document(dtype, identifier)
                if doc:
                    documents.append(doc)

        if doc_type is None:
            read_dir(self.profiles_dir, DocumentType.PROFILE)
            read_dir(self.posts_dir, DocumentType.POST)
            read_dir(self.journal_dir, DocumentType.JOURNAL)
            read_dir(self.urls_dir, DocumentType.ENRICHMENT_URL)
        elif doc_type == DocumentType.PROFILE:
            read_dir(self.profiles_dir, DocumentType.PROFILE)
        elif doc_type == DocumentType.POST:
            read_dir(self.posts_dir, DocumentType.POST)
        elif doc_type == DocumentType.JOURNAL:
            read_dir(self.journal_dir, DocumentType.JOURNAL)
        elif doc_type == DocumentType.ENRICHMENT_URL:
            read_dir(self.urls_dir, DocumentType.ENRICHMENT_URL)
        elif doc_type == DocumentType.ENRICHMENT_MEDIA:
            read_dir(self.media_dir, DocumentType.ENRICHMENT_MEDIA, "*.md")
        elif doc_type == DocumentType.MEDIA:
            if self.media_dir.exists():
                for file_path in self.media_dir.iterdir():
                    if file_path.is_file() and file_path.suffix != ".md":
                        try:
                            content = file_path.read_bytes()
                            documents.append(
                                Document(
                                    content=content.decode("utf-8", errors="ignore"),
                                    type=DocumentType.MEDIA,
                                )
                            )
                        except (OSError, UnicodeDecodeError) as exc:
                            logger.warning("Failed to read media file %s: %s", file_path, exc)
        return documents

    def _url_to_path(self, url: str, document: Document) -> Path:
        base = self._ctx.base_url.rstrip("/")
        if url.startswith(base):
            url_path = url[len(base) :]
        else:
            url_path = url

        url_path = url_path.strip("/")

        if document.type == DocumentType.POST:
            return self.site_root / f"{url_path}.md"
        if document.type == DocumentType.PROFILE:
            return self.site_root / f"{url_path}.md"
        if document.type == DocumentType.JOURNAL:
            return self.site_root / f"{url_path}.md"
        if document.type == DocumentType.ENRICHMENT_URL:
            return self.site_root / f"{url_path}.md"
        if document.type in (DocumentType.ENRICHMENT_MEDIA, DocumentType.MEDIA):
            return self.site_root / url_path
        return self.site_root / f"{url_path}.md"

    def _write_document(self, document: Document, path: Path) -> None:
        import yaml as _yaml

        path.parent.mkdir(parents=True, exist_ok=True)

        if document.type in (DocumentType.POST, DocumentType.JOURNAL):
            metadata = dict(document.metadata or {})
            if "date" in metadata:
                metadata["date"] = _format_frontmatter_datetime(metadata["date"])
            if "authors" in metadata:
                _ensure_author_entries(path.parent, metadata.get("authors"))

            yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
            full_content = f"---\n{yaml_front}---\n\n{document.content}"
            path.write_text(full_content, encoding="utf-8")
        elif document.type == DocumentType.PROFILE:
            from egregora.agents.shared.author_profiles import write_profile as write_profile_content

            author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
            if not author_uuid:
                msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
                raise ValueError(msg)
            write_profile_content(author_uuid, document.content, self.profiles_dir)
        elif document.type == DocumentType.ENRICHMENT_URL:
            if document.parent_id or document.metadata:
                metadata = document.metadata.copy()
                if document.parent_id:
                    metadata["parent_id"] = document.parent_id

                yaml_front = _yaml.dump(
                    metadata, default_flow_style=False, allow_unicode=True, sort_keys=False
                )
                full_content = f"---\n{yaml_front}---\n\n{document.content}"
                path.write_text(full_content, encoding="utf-8")
            else:
                path.write_text(document.content, encoding="utf-8")
        elif document.type == DocumentType.ENRICHMENT_MEDIA:
            path.write_text(document.content, encoding="utf-8")
        elif document.type == DocumentType.MEDIA:
            if isinstance(document.content, bytes):
                path.write_bytes(document.content)
            else:
                path.write_text(document.content, encoding="utf-8")
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

        if raw_content.startswith("---\n"):
            try:
                parts = raw_content.split("---\n", 2)
                if len(parts) >= 3:
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
            if counter > 1000:
                msg = f"Failed to resolve collision for {path} after 1000 attempts"
                raise RuntimeError(msg)


# ============================================================================
# MkDocs filesystem storage helpers
# ============================================================================

ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)


def _extract_clean_date(date_str: str) -> str:
    """Extract a clean ``YYYY-MM-DD`` date from user-provided strings."""
    import datetime
    import re

    date_str = date_str.strip()

    try:
        if len(date_str) == ISO_DATE_LENGTH and date_str[4] == "-" and date_str[7] == "-":
            datetime.date.fromisoformat(date_str)
            return date_str
    except (ValueError, AttributeError):
        pass

    match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if match:
        clean_date = match.group(1)
        try:
            datetime.date.fromisoformat(clean_date)
        except (ValueError, AttributeError):
            pass
        else:
            return clean_date

    return date_str


def _format_frontmatter_datetime(raw_date: str | date | datetime) -> str:
    """Normalize a metadata date into the RSS-friendly ``YYYY-MM-DD HH:MM`` string."""
    if raw_date is None:
        return ""

    if isinstance(raw_date, datetime):
        dt = raw_date
    elif isinstance(raw_date, date):
        dt = datetime.combine(raw_date, datetime.min.time())
    else:
        raw = str(raw_date).strip()
        if not raw:
            return ""
        try:
            dt = datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            try:
                dt = dateutil_parser.parse(raw)
            except (ImportError, ValueError, TypeError):
                return raw

    return dt.strftime("%Y-%m-%d %H:%M")


def _ensure_author_entries(output_dir: Path, author_ids: list[str] | None) -> None:
    """Ensure every referenced author has an entry in `.authors.yml`."""
    if not author_ids:
        return

    site_root = output_dir.resolve().parent
    authors_path = site_root / ".authors.yml"

    try:
        authors = yaml.safe_load(authors_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        authors = {}

    new_ids: list[str] = []
    for author_id in author_ids:
        if not author_id:
            continue
        if author_id in authors:
            continue
        authors[author_id] = {"name": author_id}
        new_ids.append(author_id)

    if not new_ids:
        return

    try:
        authors_path.parent.mkdir(parents=True, exist_ok=True)
        authors_path.write_text(
            yaml.dump(authors, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Registered %d new author(s) in %s", len(new_ids), authors_path)
    except OSError as exc:
        logger.warning("Failed to update %s: %s", authors_path, exc)


def _write_mkdocs_post(content: str, metadata: dict[str, Any], output_dir: Path) -> str:
    """Save a MkDocs blog post with YAML front matter and unique slugging."""
    required = ["title", "slug", "date"]
    for key in required:
        if key not in metadata:
            msg = f"Missing required metadata: {key}"
            raise ValueError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)

    raw_date = metadata["date"]
    date_prefix = _extract_clean_date(raw_date)

    base_slug = slugify(metadata["slug"])
    slug_candidate = base_slug
    filename = f"{date_prefix}-{slug_candidate}.md"
    filepath = safe_path_join(output_dir, filename)
    suffix = 2
    while filepath.exists():
        slug_candidate = f"{base_slug}-{suffix}"
        filename = f"{date_prefix}-{slug_candidate}.md"
        filepath = safe_path_join(output_dir, filename)
        suffix += 1

    front_matter = {
        "title": metadata["title"],
        "slug": slug_candidate,
    }

    front_matter["date"] = _format_frontmatter_datetime(raw_date)

    if "authors" in metadata:
        _ensure_author_entries(output_dir, metadata.get("authors"))

    if "tags" in metadata:
        front_matter["tags"] = metadata["tags"]
    if "summary" in metadata:
        front_matter["summary"] = metadata["summary"]
    if "authors" in metadata:
        front_matter["authors"] = metadata["authors"]
    if "category" in metadata:
        front_matter["category"] = metadata["category"]

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    full_post = f"---\n{yaml_front}---\n\n{content}"
    filepath.write_text(full_post, encoding="utf-8")
    return str(filepath)


def secure_path_join(base_dir: Path, user_path: str) -> Path:
    """Safely join ``user_path`` to ``base_dir`` preventing directory traversal."""
    full_path = (base_dir / user_path).resolve()
    try:
        full_path.relative_to(base_dir.resolve())
    except ValueError as exc:
        msg = f"Path traversal detected: {user_path!r} escapes base directory {base_dir}"
        raise ValueError(msg) from exc
    return full_path
