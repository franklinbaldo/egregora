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
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape

from egregora.config.settings import EgregoraConfig, create_default_config
from egregora.output_adapters.base import SiteConfiguration
from egregora.output_adapters.mkdocs.paths import derive_mkdocs_paths
from egregora.resources.prompts import PromptManager

logger = logging.getLogger(__name__)


class _ConfigLoader(yaml.SafeLoader):
    """YAML loader that ignores unknown tags."""


_ConfigLoader.add_constructor(None, lambda loader, node: None)


def _safe_yaml_load(content: str) -> dict[str, Any]:
    """Load YAML safely, ignoring unknown tags like !ENV."""
    return yaml.load(content, Loader=_ConfigLoader) or {}  # noqa: S506


class MkDocsSiteScaffolder:
    """Create MkDocs site structures and resolve existing layouts."""

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root contains a mkdocs.yml file."""
        if not site_root.exists():
            return False

        egregora_mkdocs = site_root / ".egregora" / "mkdocs.yml"
        if egregora_mkdocs.exists():
            return True

        legacy_path = site_root / "mkdocs.yml"
        return legacy_path.exists()

    def scaffold_site(self, site_root: Path, site_name: str, **_kwargs: object) -> tuple[Path, bool]:
        """Create the initial MkDocs site structure."""
        site_root = site_root.expanduser().resolve()
        site_root.mkdir(parents=True, exist_ok=True)

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

        try:
            templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

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
                "media_counts": {"urls": 0, "images": 0, "videos": 0, "audio": 0},
                "recent_media": [],
                "overrides_dir": Path(
                    os.path.relpath(site_paths["egregora_dir"] / "overrides", mkdocs_config_dir)
                ).as_posix(),
            }

            new_mkdocs_path = site_paths["mkdocs_config_path"]
            if not site_exists:
                mkdocs_template = env.get_template("mkdocs.yml.jinja")
                mkdocs_content = mkdocs_template.render(**context)
                new_mkdocs_path.parent.mkdir(parents=True, exist_ok=True)
                new_mkdocs_path.write_text(mkdocs_content, encoding="utf-8")
                logger.info("Created .egregora/mkdocs.yml")
            else:
                new_mkdocs_path = mkdocs_path or legacy_mkdocs

            self._create_site_structure(site_paths, env, context)
        except Exception as e:
            msg = f"Failed to scaffold MkDocs site: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info("MkDocs site scaffold checked/updated at %s", site_root)
            return (new_mkdocs_path, not site_exists)

    def scaffold(self, path: Path, config: dict) -> None:
        site_name = config.get("site_name")
        mkdocs_path, created = self.scaffold_site(path, site_name or path.name)
        if not created:
            logger.info("MkDocs site already exists at %s (config: %s)", path, mkdocs_path)

    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        """Resolve all paths for an existing MkDocs site."""
        if not self.supports_site(site_root):
            msg = f"{site_root} is not a valid MkDocs site (no mkdocs.yml found)"
            raise ValueError(msg)
        try:
            site_paths = derive_mkdocs_paths(site_root)
        except Exception as e:
            msg = f"Failed to resolve site paths: {e}"
            raise RuntimeError(msg) from e
        config_file = site_paths.get("mkdocs_path")
        mkdocs_path = site_paths.get("mkdocs_path")
        if mkdocs_path:
            try:
                mkdocs_config = _safe_yaml_load(mkdocs_path.read_text(encoding="utf-8"))
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

    def _create_site_structure(
        self, site_paths: dict[str, Path], env: Environment, context: dict[str, Any]
    ) -> None:
        self._create_egregora_structure(site_paths, env)
        self._create_content_directories(site_paths)
        self._create_template_files(site_paths, env, context)
        self._create_egregora_config(site_paths, env)

    def _create_content_directories(self, site_paths: dict[str, Path]) -> None:
        posts_dir = site_paths["posts_dir"]
        profiles_dir = site_paths["profiles_dir"]
        media_dir = site_paths["media_dir"]
        journal_dir = site_paths["journal_dir"]

        for directory in (posts_dir, profiles_dir, media_dir, journal_dir):
            directory.mkdir(parents=True, exist_ok=True)

        for subdir in ["images", "videos", "audio", "documents"]:
            media_subdir = media_dir / subdir
            media_subdir.mkdir(exist_ok=True)
            (media_subdir / ".gitkeep").touch()

        journal_dir.mkdir(exist_ok=True)
        (journal_dir / ".gitkeep").touch()

    def _create_template_files(
        self, site_paths: dict[str, Path], env: Environment, context: dict[str, Any]
    ) -> None:
        site_root = site_paths["site_root"]
        docs_dir = site_paths["docs_dir"]
        profiles_dir = site_paths["profiles_dir"]
        media_dir = site_paths["media_dir"]
        posts_dir = site_paths["posts_dir"]

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
            (site_paths["egregora_dir"] / "main.py", "main.py.jinja"),
        ]

        stylesheets_dir = docs_dir / "stylesheets"
        stylesheets_dir.mkdir(parents=True, exist_ok=True)
        custom_css_src = Path(env.loader.searchpath[0]) / "docs" / "stylesheets" / "custom.css"
        custom_css_dest = stylesheets_dir / "custom.css"
        if custom_css_src.exists() and not custom_css_dest.exists():
            shutil.copy(custom_css_src, custom_css_dest)

        javascripts_dir = docs_dir / "javascripts"
        javascripts_dir.mkdir(parents=True, exist_ok=True)
        carousel_js_src = Path(env.loader.searchpath[0]) / "docs" / "javascripts" / "media_carousel.js"
        carousel_js_dest = javascripts_dir / "media_carousel.js"
        if carousel_js_src.exists() and not carousel_js_dest.exists():
            shutil.copy(carousel_js_src, carousel_js_dest)

        for target_path, template_name in templates_to_render:
            if not target_path.exists():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                template = env.get_template(template_name)
                content = template.render(**context)
                target_path.write_text(content, encoding="utf-8")

        overrides_dest = site_paths["egregora_dir"] / "overrides"
        if not overrides_dest.exists():
            overrides_src = Path(env.loader.searchpath[0]) / "overrides"
            if overrides_src.exists():
                shutil.copytree(overrides_src, overrides_dest)

    def _create_egregora_config(self, site_paths: dict[str, Path], env: Environment) -> None:
        config_path = site_paths["config_path"]
        if not config_path.exists():
            try:
                config_template = env.get_template(".egregora/config.yml.jinja")
                config_content = config_template.render()
                config_path.write_text(config_content, encoding="utf-8")
                logger.info("Created .egregora/config.yml from template")
            except (OSError, TemplateError) as e:
                logger.warning("Failed to render config template: %s. Using Pydantic default.", e)
                create_default_config(site_paths["site_root"])

    def _create_egregora_structure(self, site_paths: dict[str, Path], env: Any | None = None) -> None:
        egregora_dir = site_paths["egregora_dir"]
        egregora_dir.mkdir(parents=True, exist_ok=True)

        if env is None:
            templates_dir = Path(__file__).resolve().parent.parent / "rendering" / "templates" / "site"
            env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape())

        prompts_dir = site_paths["prompts_dir"]
        prompts_dir.mkdir(exist_ok=True)

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


__all__ = ["MkDocsSiteScaffolder", "_safe_yaml_load"]
