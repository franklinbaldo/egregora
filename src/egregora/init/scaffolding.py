"""Site scaffolding utilities for MkDocs-based Egregora sites."""

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import DEFAULT_BLOG_DIR, SitePaths
from ..config.site import _ConfigLoader, resolve_site_paths

SITE_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "site"

DEFAULT_SITE_NAME = "Egregora Archive"
DEFAULT_DOCS_SETTING = "."  # Site root - posts will be at site/posts/ not site/docs/posts/


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
    return docs_dir, created


def _read_existing_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Return the docs directory defined by an existing mkdocs.yml."""
    try:
        payload = yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}
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

    # Setup Jinja2 environment to load templates from file system
    env = Environment(
        loader=FileSystemLoader(str(SITE_TEMPLATES_DIR)),
        autoescape=select_autoescape(),  # Only autoescape when appropriate
    )

    # Template context
    context = {
        "site_name": site_name,
        "blog_dir": DEFAULT_BLOG_DIR,
        "docs_dir": DEFAULT_DOCS_SETTING,
    }

    # Create mkdocs.yml from template (now in .egregora/)
    mkdocs_template = env.get_template(".egregora/mkdocs.yml.jinja2")
    mkdocs_content = mkdocs_template.render(**context)
    mkdocs_path.write_text(mkdocs_content, encoding="utf-8")

    # Create essential directories and files
    site_paths = resolve_site_paths(site_root)
    _create_site_structure(site_paths, env, context)

    return site_paths.docs_dir


def _create_site_structure(
    site_paths: SitePaths, env: Environment, context: dict[str, Any]
) -> None:
    """Create essential directories and index files for the blog structure."""
    docs_dir = site_paths.docs_dir
    posts_dir = site_paths.posts_dir
    profiles_dir = site_paths.profiles_dir
    media_dir = site_paths.media_dir

    for directory in {docs_dir, posts_dir, profiles_dir, media_dir}:
        directory.mkdir(parents=True, exist_ok=True)

    # Create media subdirectories with .gitkeep
    for subdir in ["images", "videos", "audio", "documents"]:
        media_subdir = media_dir / subdir
        media_subdir.mkdir(exist_ok=True)
        (media_subdir / ".gitkeep").touch()

    # Create README.md
    readme_path = site_paths.site_root / "README.md"
    if not readme_path.exists():
        template = env.get_template("README.md.jinja2")
        content = template.render(**context)
        readme_path.write_text(content, encoding="utf-8")

    # Create .gitignore
    gitignore_path = site_paths.site_root / ".gitignore"
    if not gitignore_path.exists():
        template = env.get_template(".gitignore.jinja2")
        content = template.render(**context)
        gitignore_path.write_text(content, encoding="utf-8")

    # Determine blog directory from context
    blog_dir = context.get("blog_dir", "posts")

    # Create homepage - but skip if blog is at root (blog_dir: ".")
    # because the blog index will serve as homepage
    homepage_path = docs_dir / "index.md"
    if blog_dir != "." and not homepage_path.exists():
        template = env.get_template("docs/index.md.jinja2")
        content = template.render(**context)
        homepage_path.write_text(content, encoding="utf-8")

    # Create about page
    about_path = docs_dir / "about.md"
    if not about_path.exists():
        template = env.get_template("docs/about.md.jinja2")
        content = template.render(**context)
        about_path.write_text(content, encoding="utf-8")

    # Create blog index page - Material expects this as entry point but keeps it simple
    blog_index_path = (
        posts_dir.parent / "index.md"
    )  # posts_dir is blog_dir/posts/, we want blog_dir/index.md
    if not blog_index_path.exists():
        template = env.get_template("docs/posts/index.md.jinja2")
        content = template.render(**context)
        blog_index_path.write_text(content, encoding="utf-8")

    # Create profiles index
    profiles_index_path = profiles_dir / "index.md"
    if not profiles_index_path.exists():
        template = env.get_template("docs/profiles/index.md.jinja2")
        content = template.render(**context)
        profiles_index_path.write_text(content, encoding="utf-8")

    # Create media index
    media_index_path = media_dir / "index.md"
    if not media_index_path.exists():
        template = env.get_template("docs/media/index.md.jinja2")
        content = template.render(**context)
        media_index_path.write_text(content, encoding="utf-8")

    # Render .egregora configuration templates
    _render_egregora_config(site_paths.site_root, env, context)


def _render_egregora_config(site_root: Path, env: Environment, context: dict[str, Any]) -> None:
    """Render .egregora configuration templates using Jinja2.

    Walks through the .egregora template directory and renders each file,
    preserving directory structure.
    """
    egregora_template_dir = SITE_TEMPLATES_DIR / ".egregora"
    egregora_config_dir = site_root / ".egregora"

    if not egregora_template_dir.exists():
        return

    if egregora_config_dir.exists():
        return  # Don't overwrite existing config

    # Walk through template directory
    for template_path in egregora_template_dir.rglob("*"):
        if template_path.is_file():
            # Calculate relative path from template root
            rel_path = template_path.relative_to(egregora_template_dir)
            output_path = egregora_config_dir / rel_path

            # Create parent directories
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Get template relative to SITE_TEMPLATES_DIR (for Jinja loader)
            template_rel = template_path.relative_to(SITE_TEMPLATES_DIR)

            try:
                # Render template with context
                template = env.get_template(str(template_rel))
                content = template.render(**context)
                output_path.write_text(content, encoding="utf-8")
            except Exception:
                # If rendering fails, just copy the file
                # (for binary files or non-Jinja content)
                output_path.write_bytes(template_path.read_bytes())


__all__ = ["ensure_mkdocs_project"]
