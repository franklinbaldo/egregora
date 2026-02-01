"""MkDocs site scaffolding helpers.

This module isolates one-time initialization logic from the runtime
``MkDocsAdapter`` data plane. Use :class:`MkDocsSiteScaffolder` for
site creation and path resolution; keep persistence concerns in the
adapter.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape
from yaml import YAMLError

from egregora.config.settings import EgregoraConfig, create_default_config
from egregora.output_sinks.base import SiteConfiguration
from egregora.output_sinks.exceptions import (
    FileSystemScaffoldError,
    PathResolutionError,
    ScaffoldConfigLoadError,
    ScaffoldingError,
    SiteNotSupportedError,
    TemplateRenderingError,
)
from egregora.output_sinks.mkdocs.paths import MkDocsPaths
from egregora.resources.prompts import PromptManager

logger = logging.getLogger(__name__)


class _ConfigLoader(yaml.SafeLoader):
    """YAML loader that ignores unknown tags."""


_ConfigLoader.add_constructor(None, lambda loader, _node: None)


def safe_yaml_load(content: str) -> dict[str, Any]:
    """Load YAML safely, ignoring unknown tags like !ENV."""
    # We use a custom SafeLoader that ignores unknown tags, which is safer than
    # FullLoader but still triggers S506 in some tools if not explicitly 'safe_load'.
    # However, standard safe_load doesn't support custom constructors easily without
    # global state or more complex code. Our _ConfigLoader inherits from SafeLoader.
    return yaml.load(content, Loader=_ConfigLoader) or {}  # nosec B506


class MkDocsSiteScaffolder:
    """Create MkDocs site structures and resolve existing layouts."""

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file."""
        if not site_root.exists():
            return False

        egregora_mkdocs = site_root / ".egregora" / "mkdocs.yml"
        return egregora_mkdocs.exists()

    def scaffold_site(self, site_root: Path, site_name: str, **_kwargs: object) -> tuple[Path, bool]:
        """Create the initial MkDocs site structure."""
        site_root = site_root.expanduser().resolve()
        site_root.mkdir(parents=True, exist_ok=True)

        # Fix for config leakage: Only load config if it exists LOCALLY in site_root.
        # Otherwise, use default config to avoid picking up parent configs (e.g. from repo root).
        config_path = site_root / ".egregora.toml"
        if config_path.exists():
            site_paths = MkDocsPaths(site_root)
        else:
            site_paths = MkDocsPaths(site_root, config=EgregoraConfig())

        mkdocs_path = site_paths.mkdocs_path
        site_exists = False
        if mkdocs_path and mkdocs_path.exists():
            logger.info("MkDocs site already exists at %s (config: %s)", site_root, mkdocs_path)
            site_exists = True

        try:
            templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

            docs_dir = site_paths.docs_dir
            docs_relative = Path(os.path.relpath(docs_dir, site_root)).as_posix()
            blog_relative = Path(os.path.relpath(site_paths.posts_dir, docs_dir)).as_posix()

            context = {
                "site_name": site_name or site_root.name or "Egregora Archive",
                "site_root": site_root,
                "blog_dir": blog_relative,
                "media_dir": Path(os.path.relpath(site_paths.media_dir, docs_dir)).as_posix(),
                "docs_dir": docs_relative,
                "site_url": "https://example.com",
                "now": datetime.now(UTC),
                "generated_date": datetime.now(UTC).strftime("%Y-%m-%d"),
                "default_writer_model": EgregoraConfig().models.writer,
                "media_counts": {"urls": 0, "images": 0, "videos": 0, "audio": 0},
                "recent_media": [],
                "overrides_dir": "overrides",
                "posts": [],
            }

            if not site_exists:
                mkdocs_template = env.get_template("mkdocs.yml.jinja")
                mkdocs_content = mkdocs_template.render(**context)
                mkdocs_path.parent.mkdir(parents=True, exist_ok=True)
                mkdocs_path.write_text(mkdocs_content, encoding="utf-8")
                logger.info("Created mkdocs.yml at %s", mkdocs_path)

            self._create_site_structure(site_paths, env, context)

            # Ensure .authors.yml exists after creating structure
            self._scaffold_authors_file(site_root)

        except TemplateError as e:
            # Try to get template name from exception, default to "unknown"
            template_name = getattr(e, "name", "unknown") or "unknown"
            raise TemplateRenderingError(template_name=template_name, reason=str(e)) from e
        except OSError as e:
            raise FileSystemScaffoldError(path=str(site_root), operation="write", reason=str(e)) from e
        except ScaffoldingError:
            # Re-raise known scaffolding errors without wrapping them.
            raise
        except Exception as e:
            msg = f"An unexpected error occurred during scaffolding at '{site_root}': {e}"
            raise ScaffoldingError(msg) from e
        else:
            logger.info("MkDocs site scaffold checked/updated at %s", site_root)
            return mkdocs_path, not site_exists

    def scaffold(self, path: Path, config: dict) -> None:
        site_name = config.get("site_name")
        mkdocs_path, created = self.scaffold_site(path, site_name or path.name)
        if not created:
            logger.info("MkDocs site already exists at %s (config: %s)", path, mkdocs_path)

    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        """Resolve all paths for an existing MkDocs site."""
        if not self.supports_site(site_root):
            reason = "no mkdocs.yml found"
            raise SiteNotSupportedError(site_root=str(site_root), reason=reason)
        try:
            site_paths = MkDocsPaths(site_root)
        except Exception as e:
            raise PathResolutionError(site_root=str(site_root), reason=str(e)) from e

        config_file = site_paths.mkdocs_config_path
        mkdocs_path = site_paths.mkdocs_path or config_file
        if not mkdocs_path or not config_file.exists():
            logger.debug("mkdocs.yml not found in %s", site_root)
            mkdocs_config = {}
        else:
            try:
                mkdocs_config = safe_yaml_load(config_file.read_text(encoding="utf-8"))
            except (YAMLError, OSError) as exc:
                raise ScaffoldConfigLoadError(path=str(mkdocs_path), reason=str(exc)) from exc
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

    def _create_site_structure(
        self, site_paths: MkDocsPaths, env: Environment, context: dict[str, Any]
    ) -> None:
        self._create_egregora_structure(site_paths, env)
        self._create_content_directories(site_paths)
        self._create_template_files(site_paths, env, context)
        self._create_egregora_config(site_paths, env)

    def _create_content_directories(self, site_paths: MkDocsPaths) -> None:
        posts_dir = site_paths.posts_dir
        profiles_dir = site_paths.profiles_dir
        media_dir = site_paths.media_dir
        journal_dir = site_paths.journal_dir

        for directory in (posts_dir, profiles_dir, media_dir, journal_dir):
            directory.mkdir(parents=True, exist_ok=True)

        # Create media subdirectories (ADR-0004: urls for URL enrichments)
        for subdir in ["images", "videos", "audio", "documents", "urls"]:
            media_subdir = media_dir / subdir
            media_subdir.mkdir(exist_ok=True)

    def _create_template_files(
        self, site_paths: MkDocsPaths, env: Environment, context: dict[str, Any]
    ) -> None:
        """Render and write all standard Jinja2 templates to the site structure.

        This method handles the creation of:
        - Root files (README, gitignore)
        - GitHub workflows
        - Initial content pages (index, about, feeds, etc.)
        - Static assets (favicon, default overrides)

        It uses the provided Jinja2 environment to render templates located in
        the `templates/site` directory.

        Args:
            site_paths: The resolved paths object for the target site.
            env: The Jinja2 environment configured with the template loader.
            context: The template variables to render.

        """
        site_root = site_paths.site_root
        docs_dir = site_paths.docs_dir
        media_dir = site_paths.media_dir

        templates_to_render = [
            (site_root / "README.md", "README.md.jinja"),
            (site_root / ".gitignore", ".gitignore.jinja"),
            (site_root / ".github" / "workflows" / "publish.yml", ".github/workflows/publish.yml.jinja"),
            (docs_dir / "index.md", "docs/index.md.jinja"),
            (docs_dir / "about.md", "docs/about.md.jinja"),
            (docs_dir / "feeds" / "index.md", "docs/feeds/index.md.jinja"),
            (media_dir / "index.md", "docs/media/index.md.jinja"),
            (site_paths.blog_root_dir / "index.md", "docs/posts/index.md.jinja"),
            (site_paths.blog_root_dir / "tags.md", "docs/posts/tags.md.jinja"),
            (site_paths.profiles_dir / "index.md", "docs/profiles/index.md.jinja"),
            (site_paths.journal_dir / "index.md", "docs/journal/index.md.jinja"),
            (site_paths.egregora_dir / "main.py", "main.py.jinja"),
        ]

        # Ensure directories exist
        stylesheets_dir = docs_dir / "stylesheets"
        stylesheets_dir.mkdir(parents=True, exist_ok=True)
        javascripts_dir = docs_dir / "javascripts"
        javascripts_dir.mkdir(parents=True, exist_ok=True)

        assets_dir = docs_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        # Get loader from environment (assumed to be FileSystemLoader)
        loader = cast("FileSystemLoader", env.loader)
        assets_src = Path(loader.searchpath[0]) / "assets"
        assets_dest = assets_dir
        if assets_src.exists():
            # Ensure assets are always copied, even if the directory exists.
            shutil.copytree(assets_src, assets_dest, dirs_exist_ok=True)

        for target_path, template_name in templates_to_render:
            if not target_path.exists():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                template = env.get_template(template_name)
                content = template.render(**context)
                target_path.write_text(content, encoding="utf-8")

        # Create overrides in site root (custom_dir is resolved relative to mkdocs.yml)
        overrides_dest = site_paths.site_root / "overrides"
        if not overrides_dest.exists():
            # We must use 'loader' (cast above) to access searchpath, as env.loader is generic BaseLoader
            overrides_src = Path(loader.searchpath[0]) / "overrides"
            if overrides_src.exists():
                shutil.copytree(overrides_src, overrides_dest)
            else:
                # Always create overrides dir to prevent MkDocs config errors
                overrides_dest.mkdir(parents=True, exist_ok=True)

    def _create_egregora_config(self, site_paths: MkDocsPaths, env: Environment) -> None:
        config_path = site_paths.config_path
        if not config_path.exists():
            create_default_config(site_paths.site_root)

    def _scaffold_authors_file(self, site_root: Path) -> None:
        """Create initial .authors.yml file if it doesn't exist."""
        # Use simple path resolution consistent with other tools
        docs_dir = site_root / "docs"
        if not docs_dir.exists():
            docs_dir.mkdir(parents=True, exist_ok=True)

        authors_file = docs_dir / ".authors.yml"

        if not authors_file.exists():
            # Create empty but valid YAML
            authors_file.write_text("# Authors metadata\n", encoding="utf-8")
            logger.info("Created initial authors file at %s", authors_file)

    def _create_egregora_structure(self, site_paths: MkDocsPaths, env: Environment | None = None) -> None:
        egregora_dir = site_paths.egregora_dir
        egregora_dir.mkdir(parents=True, exist_ok=True)

        if env is None:
            templates_dir = Path(__file__).resolve().parent.parent / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

        prompts_dir = site_paths.prompts_dir
        prompts_dir.mkdir(parents=True, exist_ok=True)

        PromptManager.copy_defaults(prompts_dir)

        prompts_readme = prompts_dir / "README.md"
        if not prompts_readme.exists():
            try:
                readme_template = env.get_template(".egregora/prompts/README.md.jinja")
                readme_content = readme_template.render()
                prompts_readme.write_text(readme_content, encoding="utf-8")
                logger.info("Created .egregora/prompts/README.md")
            except (OSError, TemplateError) as e:
                logger.warning("Failed to render prompts README template: %s. Using simple version.", e)
                prompts_readme.write_text(
                    "# Custom Prompts\n\n"
                    "Place custom prompt overrides here with same structure as package defaults.\n\n"
                    "See https://docs.egregora.ai for more information.\n",
                    encoding="utf-8",
                )

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


__all__ = ["MkDocsSiteScaffolder", "safe_yaml_load"]
