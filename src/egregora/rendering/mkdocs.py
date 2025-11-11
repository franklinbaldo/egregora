"""MkDocs output format implementation.

This module contains both the MkDocs output format coordinator and its storage
implementations. All MkDocs-specific code lives here, following the principle
that format-specific implementations should be colocated.
"""

from __future__ import annotations

import logging
import uuid as uuid_lib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape

from egregora.agents.shared.profiler import write_profile as write_profile_content
from egregora.config.loader import create_default_config
from egregora.rendering.base import OutputFormat, SiteConfiguration
from egregora.rendering.mkdocs_site import load_mkdocs_config, resolve_site_paths
from egregora.utils.paths import slugify
from egregora.utils.write_post import write_post as write_mkdocs_post

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.storage import EnrichmentStorage, JournalStorage, PostStorage, ProfileStorage

logger = logging.getLogger(__name__)


# ============================================================================
# MkDocs Storage Implementations
# ============================================================================
# These classes implement the storage protocols for MkDocs filesystem structure.
# They are used internally by MkDocsOutputFormat and should not be imported directly.


class MkDocsPostStorage:
    """Filesystem-based post storage following MkDocs conventions.

    Structure:
        site_root/posts/{date}-{slug}.md

    Posts are stored as markdown files with YAML frontmatter:
        ---
        title: My Post
        date: 2025-01-10
        tags: [tag1, tag2]
        ---

        Post content here...
    """

    def __init__(self, site_root: Path, output_format: OutputFormat | None = None) -> None:
        """Initialize MkDocs post storage.

        Args:
            site_root: Root directory for MkDocs site
            output_format: OutputFormat instance for utilities (normalize_slug, etc.)
                          If None, will use default implementations without validations

        Side Effects:
            Creates posts/ directory if it doesn't exist

        """
        self.site_root = site_root
        self.posts_dir = site_root / "posts"
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.output_format = output_format

    def write(self, slug: str, metadata: dict, content: str) -> str:
        """Write post to filesystem with data integrity validations.

        Args:
            slug: URL-friendly slug (e.g., "my-post")
            metadata: YAML frontmatter dict (date optional, defaults to today)
            content: Markdown content (body only)

        Returns:
            Relative path string (e.g., "posts/2025-01-10-my-post.md")

        Note:
            Uses OutputFormat utilities for:
            - Slug normalization (URL-safe, lowercase, hyphens)
            - Date extraction (handles window labels, ISO timestamps, defaults to today)
            - Unique filename generation (prevents silent overwrites)
            - Frontmatter slug sync (updates metadata to match normalized filename)

        Important:
            The metadata dict is MUTATED to keep frontmatter slug in sync with filename.
            If filename is "2025-01-10-my-post-2.md" (collision suffix added),
            metadata["slug"] will be updated to "my-post-2" to match.

        """
        # Extract date from metadata (optional, defaults to today via extract_date_prefix)
        date_str = metadata.get("date", "")

        # Apply data integrity validations if OutputFormat is available
        if self.output_format:
            # Normalize slug to URL-safe format
            normalized_slug = self.output_format.normalize_slug(slug)

            # Extract clean YYYY-MM-DD date prefix (handles empty string → today's date)
            date_prefix = self.output_format.extract_date_prefix(str(date_str))

            # Generate unique filename with date prefix
            filename_pattern = f"{date_prefix}-{normalized_slug}.md"
            path = self.output_format.generate_unique_filename(self.posts_dir, filename_pattern)

            # Extract final slug from path (may have collision suffix)
            # Example: "2025-01-10-my-post-2.md" → "my-post-2"
            final_filename = path.stem  # Remove .md extension
            # Remove date prefix: "2025-01-10-my-post-2" → "my-post-2"
            if final_filename.startswith(date_prefix):
                final_slug = final_filename[len(date_prefix) + 1 :]  # +1 for the hyphen
            else:
                final_slug = final_filename

            # CRITICAL: Update metadata slug to match final filename
            # This ensures frontmatter stays in sync with filename
            # URLs, RAG chunk IDs, and all downstream tools depend on this
            metadata = metadata.copy()  # Don't mutate caller's dict
            metadata["slug"] = final_slug
        else:
            # Fallback: simple filename without validations
            path = self.posts_dir / f"{slug}.md"

        # Combine frontmatter + content
        frontmatter = yaml.dump(metadata, sort_keys=False, allow_unicode=True)
        full_content = f"---\n{frontmatter}---\n\n{content}"

        # Atomic write
        path.write_text(full_content, encoding="utf-8")

        # Return relative path as identifier
        return str(path.relative_to(self.site_root))

    def read(self, slug: str) -> tuple[dict, str] | None:
        """Read post from filesystem.

        Args:
            slug: URL-friendly slug (matches files with or without date prefix)

        Returns:
            (metadata dict, content string) if post exists, None otherwise

        Note:
            Searches for both date-prefixed ({date}-{slug}.md) and simple ({slug}.md) formats.
            This provides backwards compatibility with posts written before data integrity updates.
            When multiple matches exist, returns the most recently modified file (deterministic).

        """
        # Try finding date-prefixed file first (new format)
        matching_files = list(self.posts_dir.glob(f"*-{slug}.md"))
        if matching_files:
            # Use most recent file if multiple matches (sort by mtime, descending)
            # Ensures deterministic behavior when duplicate slugs exist
            path = max(matching_files, key=lambda p: p.stat().st_mtime)
        else:
            # Fall back to simple format (legacy)
            path = self.posts_dir / f"{slug}.md"

        if not path.exists():
            return None

        # Parse frontmatter
        raw_content = path.read_text(encoding="utf-8")
        return self._parse_frontmatter(raw_content)

    def exists(self, slug: str) -> bool:
        """Check if post exists.

        Args:
            slug: URL-friendly slug (matches files with or without date prefix)

        Returns:
            True if post exists in either date-prefixed or simple format

        Note:
            Checks both {date}-{slug}.md (new format) and {slug}.md (legacy format).

        """
        # Check for date-prefixed format first
        matching_files = list(self.posts_dir.glob(f"*-{slug}.md"))
        if matching_files:
            return True

        # Fall back to simple format
        return (self.posts_dir / f"{slug}.md").exists()

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from markdown content.

        Args:
            content: Raw markdown with frontmatter

        Returns:
            (metadata dict, body string)

        Raises:
            ValueError: If frontmatter is malformed

        """
        if not content.startswith("---\n"):
            return {}, content

        # Find end of frontmatter
        end_marker = content.find("\n---\n", 4)
        if end_marker == -1:
            # No closing marker
            return {}, content

        # Extract and parse frontmatter
        frontmatter_text = content[4:end_marker]
        body = content[end_marker + 5 :].lstrip()

        try:
            metadata = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            msg = f"Invalid YAML frontmatter: {e}"
            raise ValueError(msg) from e

        return metadata, body


class MkDocsProfileStorage:
    """Filesystem-based profile storage with YAML frontmatter and .authors.yml support.

    Structure:
        site_root/profiles/{uuid}.md
        site_root/.authors.yml

    Profiles are stored with YAML frontmatter containing metadata (name, alias, avatar, bio, social).
    The .authors.yml file is automatically updated for MkDocs blog plugin compatibility.
    """

    def __init__(self, site_root: Path) -> None:
        """Initialize MkDocs profile storage.

        Args:
            site_root: Root directory for MkDocs site

        Side Effects:
            Creates profiles/ directory if it doesn't exist

        """
        self.site_root = site_root
        self.profiles_dir = site_root / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def write(self, author_uuid: str, content: str) -> str:
        """Write profile to filesystem with YAML frontmatter and .authors.yml update.

        Preserves existing profile metadata (alias, avatar, bio, social) by extracting
        it from the existing profile file before writing the new content. Updates
        .authors.yml for MkDocs blog plugin compatibility.

        Args:
            author_uuid: Anonymized author UUID
            content: Markdown profile content (without frontmatter)

        Returns:
            Relative path string (e.g., "profiles/abc-123.md")

        Side Effects:
            - Writes profile with YAML frontmatter
            - Updates .authors.yml in site root

        """
        # Use write_profile_content to ensure proper YAML frontmatter and .authors.yml update
        absolute_path = write_profile_content(author_uuid, content, self.profiles_dir)
        return str(Path(absolute_path).relative_to(self.site_root))

    def read(self, author_uuid: str) -> str | None:
        """Read profile from filesystem.

        Args:
            author_uuid: Anonymized author UUID

        Returns:
            Markdown content if profile exists, None otherwise

        """
        path = self.profiles_dir / f"{author_uuid}.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def exists(self, author_uuid: str) -> bool:
        """Check if profile exists.

        Args:
            author_uuid: Anonymized author UUID

        Returns:
            True if {profiles_dir}/{uuid}.md exists

        """
        return (self.profiles_dir / f"{author_uuid}.md").exists()


class MkDocsJournalStorage:
    """Filesystem-based journal storage.

    Structure:
        site_root/posts/journal/journal_{safe_label}.md

    Journals are stored inside the posts/journal/ directory so they appear
    in the blog navigation alongside posts.

    Window labels like "2025-01-10 10:00 to 12:00" are converted to
    safe filenames like "journal_2025-01-10_10-00_to_12-00.md".
    """

    def __init__(self, site_root: Path) -> None:
        """Initialize MkDocs journal storage.

        Args:
            site_root: Root directory for MkDocs site

        Side Effects:
            Creates posts/journal/ directory if it doesn't exist

        """
        self.site_root = site_root
        self.journal_dir = site_root / "posts" / "journal"
        self.journal_dir.mkdir(parents=True, exist_ok=True)

    def write(self, window_label: str, content: str) -> str:
        """Write journal entry to filesystem.

        Args:
            window_label: Human-readable window label
                         (e.g., "2025-01-10 10:00 to 12:00")
            content: Markdown journal content

        Returns:
            Relative path string (e.g., "posts/journal/journal_2025-01-10_10-00_to_12-00.md")

        """
        # Convert window label to filename-safe format
        safe_label = self._sanitize_label(window_label)
        path = self.journal_dir / f"journal_{safe_label}.md"
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.site_root))

    @staticmethod
    def _sanitize_label(label: str) -> str:
        """Convert window label to filename-safe string.

        Args:
            label: Human-readable label (e.g., "2025-01-10 10:00 to 12:00")

        Returns:
            Safe filename (e.g., "2025-01-10_10-00_to_12-00")

        """
        return label.replace(" ", "_").replace(":", "-")


class MkDocsEnrichmentStorage:
    """Filesystem-based enrichment storage.

    Structure:
        site_root/media/urls/{enrichment_id}.md    # URL enrichments
        site_root/docs/media/{filename}.md         # Media enrichments

    URL enrichments are stored in media/urls/ and published via mkdocs.yml configuration.
    Media enrichments are stored inside docs/media/ for automatic publication.

    To publish URL enrichments, configure mkdocs.yml with:
        docs_dir: '.'  # Publish from site root

    Or add media/ to your navigation structure.

    URL enrichments use deterministic UUIDs based on the URL.
    Media enrichments are stored next to the media file with .md extension.
    """

    def __init__(self, site_root: Path) -> None:
        """Initialize MkDocs enrichment storage.

        Args:
            site_root: Root directory for MkDocs site

        Side Effects:
            Creates media/urls/ directory if it doesn't exist

        """
        self.site_root = site_root
        self.urls_dir = site_root / "media" / "urls"
        self.urls_dir.mkdir(parents=True, exist_ok=True)

    def write_url_enrichment(self, url: str, content: str) -> str:
        """Write URL enrichment to filesystem.

        Args:
            url: Full URL that was enriched
            content: Markdown enrichment content

        Returns:
            Relative path string (e.g., "media/urls/example-com-article-a1b2c3d4.md")

        Note:
            Uses readable prefix (40 chars) + hash suffix (16 chars) for collision-free,
            partially human-readable filenames. The hash ensures uniqueness even when
            URLs share the same prefix (e.g., long query strings, different fragments).

        Examples:
            - https://example.com/article
              → media/urls/https-example-com-article-a1b2c3d4e5f6g7h8.md
            - https://docs.python.org/3/library/pathlib.html
              → media/urls/https-docs-python-org-3-library-pathl-b2c3d4e5f6g7h8i9.md
            - https://example.com/article?id=12345678901234567890  (collision-prone with slug-only)
              → media/urls/https-example-com-article-id-123456-c3d4e5f6g7h8i9j0.md

        """
        # Create human-readable prefix (40 chars) + collision-proof hash suffix (8 chars)
        # Uses UUID5 for deterministic, discoverable hash (same as document_id)
        url_prefix = slugify(url, max_len=40)
        url_uuid = str(uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, url))
        url_hash = url_uuid.replace("-", "")[:8]  # Take first 8 hex chars (32 bits)
        filename = f"{url_prefix}-{url_hash}.md"

        path = self.urls_dir / filename
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.site_root))

    def write_media_enrichment(self, filename: str, content: str) -> str:
        """Write media enrichment to filesystem.

        Args:
            filename: Path to media file relative to site_root (e.g., "media/images/abc.jpg")
            content: Markdown enrichment content

        Returns:
            Relative path string (e.g., "media/images/abc.jpg.md")

        Note:
            Enrichment is stored next to the media file with .md extension.
            Parent directories are created if needed.

            Modern MkDocs layout uses `docs_dir: '.'` so media files are at
            site_root/media/... and enrichments go to site_root/media/.../file.md

        """
        # Media enrichment goes next to the media file
        # filename is already relative to site_root (e.g., "media/images/abc.jpg")
        media_path = self.site_root / filename
        enrichment_path = media_path.with_suffix(media_path.suffix + ".md")

        # Ensure parent directory exists
        enrichment_path.parent.mkdir(parents=True, exist_ok=True)

        enrichment_path.write_text(content, encoding="utf-8")
        return str(enrichment_path.relative_to(self.site_root))


# ============================================================================
# MkDocs Output Format Coordinator
# ============================================================================


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
            msg = "MkDocsOutputFormat not initialized - call initialize(site_root) first"
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
            msg = "MkDocsOutputFormat not initialized - call initialize(site_root) first"
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
            msg = "MkDocsOutputFormat not initialized - call initialize(site_root) first"
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
        - .egregora/prompts/system/ (writer, editor prompts)
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
            msg = "MkDocsOutputFormat not initialized - call initialize() first"
            raise RuntimeError(msg)

        # MkDocs identifiers are relative paths from site_root
        return (self._site_root / identifier).resolve()
