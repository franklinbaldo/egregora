"""Site scaffolding utilities for MkDocs-based Egregora sites."""

import logging
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.config import DEFAULT_BLOG_DIR, SitePaths
from egregora.config.loader import create_default_config
from egregora.config.site import _ConfigLoader, resolve_site_paths

logger = logging.getLogger(__name__)
SITE_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "rendering" / "templates" / "site"
DEFAULT_SITE_NAME = "Egregora Archive"
DEFAULT_DOCS_SETTING = "docs"


def ensure_mkdocs_project(site_root: Path) -> tuple[Path, bool]:
    """Ensure site_root contains an MkDocs configuration.

    Returns the directory where documentation content should be written and a flag
    indicating whether the configuration was created during this call.
    """
    site_root = site_root.expanduser().resolve()
    site_root.mkdir(parents=True, exist_ok=True)
    mkdocs_path = site_root / "mkdocs.yml"
    created = False
    if mkdocs_path.exists():
        docs_dir = _read_existing_mkdocs(mkdocs_path, site_root)
    else:
        docs_dir = _create_default_mkdocs(mkdocs_path, site_root)
        created = True
    docs_dir.mkdir(parents=True, exist_ok=True)
    return (docs_dir, created)


def _read_existing_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Return the docs directory defined by an existing mkdocs.yml."""
    try:
        payload = yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}  # noqa: S506  # _ConfigLoader extends SafeLoader
    except yaml.YAMLError:
        payload = {}
    docs_dir_setting = payload.get("docs_dir")
    if docs_dir_setting is None or docs_dir_setting in {".", ""}:
        return site_root
    docs_dir = Path(str(docs_dir_setting))
    if not docs_dir.is_absolute():
        docs_dir = (site_root / docs_dir).resolve()
    return docs_dir


def _create_default_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Create a comprehensive MkDocs configuration for blog and return the docs directory path."""
    site_name = site_root.name or DEFAULT_SITE_NAME
    env = Environment(loader=FileSystemLoader(str(SITE_TEMPLATES_DIR)), autoescape=select_autoescape())
    context = {"site_name": site_name, "blog_dir": DEFAULT_BLOG_DIR, "docs_dir": DEFAULT_DOCS_SETTING}
    mkdocs_template = env.get_template("mkdocs.yml.jinja")
    mkdocs_content = mkdocs_template.render(**context)
    mkdocs_path.write_text(mkdocs_content, encoding="utf-8")
    site_paths = resolve_site_paths(site_root)
    _create_site_structure(site_paths, env, context)
    return site_paths.docs_dir


def _create_site_structure(site_paths: SitePaths, env: Environment, context: dict[str, Any]) -> None:
    """Create essential directories and index files for the blog structure.

    SIMPLIFIED (Alpha): Always create .egregora/ structure.
    """
    # Create .egregora/ structure (new!)
    _create_egregora_structure(site_paths)

    # Create docs/ structure
    docs_dir = site_paths.docs_dir
    posts_dir = site_paths.posts_dir
    profiles_dir = site_paths.profiles_dir
    media_dir = site_paths.media_dir
    for directory in (docs_dir, posts_dir, profiles_dir, media_dir):
        directory.mkdir(parents=True, exist_ok=True)
    for subdir in ["images", "videos", "audio", "documents"]:
        media_subdir = media_dir / subdir
        media_subdir.mkdir(exist_ok=True)
        (media_subdir / ".gitkeep").touch()
    readme_path = site_paths.site_root / "README.md"
    if not readme_path.exists():
        template = env.get_template("README.md.jinja")
        content = template.render(**context)
        readme_path.write_text(content, encoding="utf-8")
    gitignore_path = site_paths.site_root / ".gitignore"
    if not gitignore_path.exists():
        template = env.get_template(".gitignore.jinja")
        content = template.render(**context)
        gitignore_path.write_text(content, encoding="utf-8")
    blog_dir = context.get("blog_dir", "posts")
    if blog_dir != ".":
        homepage_path = docs_dir / "index.md"
        if not homepage_path.exists():
            template = env.get_template("docs/index.md.jinja")
            content = template.render(**context)
            homepage_path.write_text(content, encoding="utf-8")
    about_path = docs_dir / "about.md"
    if not about_path.exists():
        template = env.get_template("docs/about.md.jinja")
        content = template.render(**context)
        about_path.write_text(content, encoding="utf-8")
    profiles_index_path = profiles_dir / "index.md"
    if not profiles_index_path.exists():
        template = env.get_template("docs/profiles/index.md.jinja")
        content = template.render(**context)
        profiles_index_path.write_text(content, encoding="utf-8")
    media_index_path = media_dir / "index.md"
    if not media_index_path.exists():
        template = env.get_template("docs/media/index.md.jinja")
        content = template.render(**context)
        media_index_path.write_text(content, encoding="utf-8")
    _render_egregora_config(site_paths.site_root, env, context)


def _create_egregora_structure(site_paths: SitePaths) -> None:
    """Create .egregora/ directory structure (SIMPLIFIED - Alpha version).

    Creates:
    - .egregora/config.yml (Pydantic-generated default config)
    - .egregora/prompts/ (for custom prompt overrides)
    - .egregora/prompts/README.md
    - .egregora/.gitignore (ignore ephemeral data)
    """
    egregora_dir = site_paths.egregora_dir
    egregora_dir.mkdir(parents=True, exist_ok=True)

    # Create prompts directory
    prompts_dir = site_paths.prompts_dir
    prompts_dir.mkdir(exist_ok=True)

    # Create prompts README
    prompts_readme = prompts_dir / "README.md"
    if not prompts_readme.exists():
        prompts_readme.write_text(
            "# Custom Prompts\n\n"
            "Place custom prompt overrides here with same names as package defaults.\n\n"
            "Available prompts:\n"
            "- `writer.md` - Main blog post writer prompt\n"
            "- `enricher_url.md` - URL enrichment prompt\n"
            "- `enricher_media.md` - Media enrichment prompt\n\n"
            "The custom prompt will be used instead of the package default.\n",
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

    # Create default config.yml using Pydantic config loader
    config_path = site_paths.config_path
    if not config_path.exists():
        create_default_config(site_paths.site_root)
        logger.info("Created default .egregora/config.yml")


def _render_egregora_config(site_root: Path, env: Environment, context: dict[str, Any]) -> None:
    """Legacy: Render .egregora configuration templates using Jinja2.

    DEPRECATED (Alpha): Use _create_egregora_structure instead.
    Kept temporarily for compatibility during transition.
    """
    # This function is now a no-op - _create_egregora_structure handles it


__all__ = ["ensure_mkdocs_project"]
