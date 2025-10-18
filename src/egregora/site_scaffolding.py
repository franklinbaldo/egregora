"""Utilities for preparing MkDocs-compatible output folders."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

DEFAULT_SITE_NAME = "Egregora Archive"
DEFAULT_BLOG_DIR = "posts"
DEFAULT_DOCS_DIR = "docs"


def ensure_mkdocs_project(site_root: Path) -> tuple[Path, bool]:
    """Ensure *site_root* contains an MkDocs configuration.

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
    return docs_dir, created


def _read_existing_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Return the docs directory defined by an existing ``mkdocs.yml``."""

    try:
        payload = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        payload = {}

    docs_dir_setting = payload.get("docs_dir")
    if docs_dir_setting in (None, "", "."):
        return site_root

    docs_dir = Path(docs_dir_setting)
    if not docs_dir.is_absolute():
        docs_dir = (site_root / docs_dir).resolve()
    return docs_dir


def _create_default_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Create a comprehensive MkDocs configuration for blog and return the docs directory path."""

    site_name = site_root.name or DEFAULT_SITE_NAME

    # Setup Jinja2 environment to load templates
    env = Environment(
        loader=PackageLoader("egregora", "templates"),
        autoescape=select_autoescape(["html", "xml", "md", "yml", "yaml", "toml"]),
    )

    # Template context
    context = {"site_name": site_name, "blog_dir": DEFAULT_BLOG_DIR}

    # Create mkdocs.yml from template
    mkdocs_template = env.get_template("mkdocs.yml.jinja2")
    mkdocs_content = mkdocs_template.render(**context)
    mkdocs_path.write_text(mkdocs_content, encoding="utf-8")

    # Create pyproject.toml from template
    pyproject_path = site_root / "pyproject.toml"
    if not pyproject_path.exists():
        pyproject_template = env.get_template("pyproject.toml.jinja2")
        pyproject_content = pyproject_template.render(**context)
        pyproject_path.write_text(pyproject_content, encoding="utf-8")

    # Create essential directories and files
    _create_site_structure(site_root)

    return site_root


def _create_site_structure(site_root: Path) -> None:
    """Create essential directories and index files for the blog structure."""

    # Create directories
    docs_dir = site_root / DEFAULT_DOCS_DIR
    posts_dir = site_root / DEFAULT_BLOG_DIR
    profiles_dir = site_root / "profiles"
    media_dir = site_root / "media"

    for directory in [docs_dir, posts_dir, profiles_dir, media_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Setup Jinja2 environment to load templates from the `templates` directory
    # within the `egregora` package.
    env = Environment(
        loader=PackageLoader("egregora", "templates"),
        autoescape=select_autoescape(["html", "xml", "md"]),
    )

    # Template context
    context = {"site_name": site_root.name, "blog_dir": DEFAULT_BLOG_DIR}

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
    blog_index_path = posts_dir / "index.md"
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
