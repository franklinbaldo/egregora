"""MkDocs output format implementation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..augmentation.profiler import write_profile as write_profile_content
from ..config.site import (
    DEFAULT_BLOG_DIR,
    DEFAULT_DOCS_DIR,
    MEDIA_DIR_NAME,
    PROFILES_DIR_NAME,
    load_mkdocs_config,
    resolve_site_paths,
)
from ..core.output_format import OutputFormat, SiteConfiguration
from ..orchestration.write_post import write_post as write_mkdocs_post
from .scaffolding import ensure_mkdocs_project

logger = logging.getLogger(__name__)


class MkDocsOutputFormat(OutputFormat):
    """MkDocs output format with Material theme support.

    Creates blog sites using:
    - MkDocs static site generator
    - Material for MkDocs theme
    - Blog plugin for post management
    - YAML front matter for metadata
    """

    @property
    def format_type(self) -> str:
        """Return 'mkdocs' as the format type identifier."""
        return "mkdocs"

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file.

        Args:
            site_root: Path to check

        Returns:
            True if mkdocs.yml exists in site_root or parent directories
        """
        if not site_root.exists():
            return False

        # Check if mkdocs.yml exists
        mkdocs_path = site_root / "mkdocs.yml"
        if mkdocs_path.exists():
            return True

        # Check parent directories
        config, mkdocs_path_found = load_mkdocs_config(site_root)
        return mkdocs_path_found is not None

    def scaffold_site(
        self, site_root: Path, site_name: str, **kwargs
    ) -> tuple[Path, bool]:
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
            docs_dir, created = ensure_mkdocs_project(site_root)
        except Exception as e:
            raise RuntimeError(f"Failed to scaffold MkDocs site: {e}") from e

        mkdocs_path = site_root / "mkdocs.yml"
        return mkdocs_path, created

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
            raise ValueError(
                f"{site_root} is not a valid MkDocs site (no mkdocs.yml found)"
            )

        try:
            site_paths = resolve_site_paths(site_root)
        except Exception as e:
            raise RuntimeError(f"Failed to resolve site paths: {e}") from e

        # Convert SitePaths to SiteConfiguration
        config_file = site_paths.mkdocs_path

        return SiteConfiguration(
            site_root=site_paths.site_root,
            site_name=site_paths.config.get("site_name", "Egregora Site"),
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

    def write_post(
        self,
        content: str,
        metadata: dict[str, Any],
        output_dir: Path,
        **kwargs,
    ) -> str:
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
            raise RuntimeError(f"Failed to write MkDocs post: {e}") from e

    def write_profile(
        self,
        author_id: str,
        profile_data: dict[str, Any],
        profiles_dir: Path,
        **kwargs,
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
            raise ValueError("author_id cannot be empty")

        # Extract content from profile_data
        if isinstance(profile_data, str):
            # If profile_data is a string, use it as content directly
            content = profile_data
        elif "content" in profile_data:
            content = profile_data["content"]
        else:
            # Build simple profile from metadata
            name = profile_data.get("name", author_id)
            bio = profile_data.get("bio", "")
            content = f"# {name}\n\n{bio}"

        try:
            return write_profile_content(author_id, content, profiles_dir)
        except Exception as e:
            raise RuntimeError(f"Failed to write profile: {e}") from e

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
            raise FileNotFoundError(
                f"No mkdocs.yml found in {site_root} or parent directories"
            )

        return config

    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for MkDocs Material theme.

        Returns:
            List of markdown extension identifiers
        """
        return [
            # Standard extensions
            "tables",
            "fenced_code",
            "footnotes",
            "attr_list",
            "md_in_html",
            "def_list",
            "toc",
            # PyMdown Extensions (Material theme)
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
            # Admonitions
            "admonition",
        ]
