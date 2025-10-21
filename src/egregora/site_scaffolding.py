"""Utilities for preparing MkDocs-compatible output folders."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from jinja2 import Environment, PackageLoader, select_autoescape

if TYPE_CHECKING:
    from egregora.config import SiteConfig

# Deprecated constants: use SiteConfig instead
DEFAULT_SITE_NAME = "Egregora Archive"
DEFAULT_BLOG_DIR = "blog"
DEFAULT_DOCS_DIR = "docs"


def ensure_mkdocs_project(
    site_root: Path, site_config: SiteConfig | None = None
) -> tuple[Path, bool]:
    """Ensure *site_root* contains an MkDocs configuration.

    Returns the directory where documentation content should be written and a flag
    indicating whether the configuration was created during this call.
    """
    # Import here to avoid circular dependency
    from egregora.config import SiteConfig

    if site_config is None:
        site_config = SiteConfig()

    site_root = site_root.expanduser().resolve()
    site_root.mkdir(parents=True, exist_ok=True)

    mkdocs_path = site_root / "mkdocs.yml"
    created = False

    if mkdocs_path.exists():
        docs_dir = _read_existing_mkdocs(mkdocs_path, site_root, site_config)
    else:
        docs_dir = _create_default_mkdocs(mkdocs_path, site_root, site_config)
        created = True

    docs_dir.mkdir(parents=True, exist_ok=True)
    return docs_dir, created


def _read_existing_mkdocs(mkdocs_path: Path, site_root: Path, site_config: SiteConfig) -> Path:
    """Return the docs directory defined by an existing ``mkdocs.yml``."""

    try:
        payload = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        payload = {}

    docs_dir_setting = payload.get("docs_dir")
    if docs_dir_setting in (None, ""):
        # MkDocs defaults to "docs" when docs_dir is not specified
        return site_root / site_config.docs_dir
    if docs_dir_setting == ".":
        return site_root

    docs_dir = Path(docs_dir_setting)
    if not docs_dir.is_absolute():
        docs_dir = (site_root / docs_dir).resolve()
    return docs_dir


def _create_default_mkdocs(mkdocs_path: Path, site_root: Path, site_config: SiteConfig) -> Path:
    """Create a comprehensive MkDocs configuration for blog and return the docs directory path."""

    site_name = site_root.name or site_config.site_name

    # Setup Jinja2 environment to load templates
    env = Environment(
        loader=PackageLoader("egregora", "templates"),
        autoescape=select_autoescape(["html", "xml", "md", "yml", "yaml", "toml"]),
    )

    # Template context with SiteConfig values
    context = {
        "site_name": site_name,
        "site_description": site_config.get_site_description(site_name),
        "blog_dir": site_config.blog_dir,
        "theme_name": site_config.theme_name,
        "theme_language": site_config.theme_language,
        "theme_primary_color": site_config.theme_primary_color,
        "theme_accent_color": site_config.theme_accent_color,
        "post_url_format": site_config.post_url_format,
        "post_url_date_format": site_config.post_url_date_format,
        "post_date_format": site_config.post_date_format,
        "posts_per_page": site_config.posts_per_page,
        "blog_nav_title": site_config.blog_nav_title,
        "profiles_nav_title": site_config.profiles_nav_title,
        "about_nav_title": site_config.about_nav_title,
    }

    # Create mkdocs.yml from template
    mkdocs_template = env.get_template("mkdocs.yml.jinja2")
    mkdocs_content = mkdocs_template.render(**context)
    mkdocs_path.write_text(mkdocs_content, encoding="utf-8")

    # Optionally validate generated config with MkDocs
    # This ensures compatibility but we don't make it fail the build
    try:
        from mkdocs.config import load_config

        loaded_config = load_config(str(mkdocs_path))
        # Validation successful - config is compatible with MkDocs
    except ImportError:
        # MkDocs not installed in this environment - skip validation
        pass
    except Exception as e:
        # Log warning but don't fail - template might have valid YAML
        # that MkDocs doesn't fully understand yet
        import logging

        logging.getLogger(__name__).warning(f"Generated mkdocs.yml validation warning: {e}")

    # Create pyproject.toml from template
    pyproject_path = site_root / "pyproject.toml"
    if not pyproject_path.exists():
        pyproject_template = env.get_template("pyproject.toml.jinja2")
        pyproject_content = pyproject_template.render(**context)
        pyproject_path.write_text(pyproject_content, encoding="utf-8")

    # Create README.md from template
    readme_path = site_root / "README.md"
    if not readme_path.exists():
        readme_template = env.get_template("README.md.jinja2")
        readme_content = readme_template.render(**context)
        readme_path.write_text(readme_content, encoding="utf-8")

    # Create essential directories and files
    _create_site_structure(site_root, site_config)

    return site_root / site_config.docs_dir


def _create_site_structure(site_root: Path, site_config: SiteConfig) -> None:
    """Create essential directories and index files for the blog structure."""

    # Create directories using SiteConfig
    docs_dir = site_root / site_config.docs_dir
    blog_dir = docs_dir / site_config.blog_dir
    blog_posts_dir = blog_dir / site_config.posts_subdir
    profiles_dir = docs_dir / "profiles"  # Place profiles inside docs/ for proper linking
    media_dir = site_root / "media"

    for directory in [docs_dir, blog_dir, blog_posts_dir, profiles_dir, media_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Setup Jinja2 environment to load templates from the `templates` directory
    # within the `egregora` package.
    env = Environment(
        loader=PackageLoader("egregora", "templates"),
        autoescape=select_autoescape(["html", "xml", "md"]),
    )

    # Template context
    context = {
        "site_name": site_root.name,
        "blog_dir": site_config.blog_dir,
        "blog_nav_title": site_config.blog_nav_title,
        "profiles_nav_title": site_config.profiles_nav_title,
        "about_nav_title": site_config.about_nav_title,
    }

    # Create homepage
    homepage_path = docs_dir / "index.md"
    if not homepage_path.exists():
        template = env.get_template("homepage.md.jinja2")
        content = template.render(**context)
        homepage_path.write_text(content, encoding="utf-8")

    # Create about page
    about_path = docs_dir / "about.md"
    if not about_path.exists():
        template = env.get_template("about.md.jinja2")
        content = template.render(**context)
        about_path.write_text(content, encoding="utf-8")

    # Create blog index
    blog_index_path = blog_dir / "index.md"
    if not blog_index_path.exists():
        template = env.get_template("blog_index.md.jinja2")
        content = template.render(**context)
        blog_index_path.write_text(content, encoding="utf-8")

    # Create profiles index
    profiles_index_path = profiles_dir / "index.md"
    if not profiles_index_path.exists():
        template = env.get_template("profiles_index.md.jinja2")
        content = template.render(**context)
        profiles_index_path.write_text(content, encoding="utf-8")


__all__ = ["ensure_mkdocs_project"]
