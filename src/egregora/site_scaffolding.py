"""Utilities for preparing MkDocs-compatible output folders."""

from __future__ import annotations

from pathlib import Path

import yaml
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


# TODO: The MkDocs configuration is hardcoded here. It would be better to have
# this as a template file (e.g., mkdocs.yml.jinja2) and use Jinja2 to render it.
def _create_default_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Create a comprehensive MkDocs configuration for blog and return the docs directory path."""

    site_name = site_root.name or DEFAULT_SITE_NAME

    # Create comprehensive blog-ready configuration
    config = {
        "site_name": site_name,
        "site_description": f"Diários da consciência coletiva - {site_name}",
        "docs_dir": ".",
        "site_dir": "site",
        "theme": {
            "name": "material",
            "language": "pt-BR",
            "palette": [
                {
                    "media": "(prefers-color-scheme: light)",
                    "scheme": "default",
                    "primary": "indigo",
                    "accent": "blue",
                    "toggle": {"icon": "material/brightness-7", "name": "Mudar para modo escuro"},
                },
                {
                    "media": "(prefers-color-scheme: dark)",
                    "scheme": "slate",
                    "primary": "indigo",
                    "accent": "blue",
                    "toggle": {"icon": "material/brightness-4", "name": "Mudar para modo claro"},
                },
            ],
            "features": [
                "navigation.instant",
                "navigation.tracking",
                "navigation.tabs",
                "navigation.sections",
                "navigation.indexes",
                "navigation.top",
                "search.highlight",
                "search.share",
                "content.code.copy",
                "content.action.edit",
                "content.action.view",
            ],
        },
        "plugins": [
            {"search": {"lang": "pt"}},
            {
                "blog": {
                    "blog_dir": DEFAULT_BLOG_DIR,
                    "blog_toc": True,
                    "post_date_format": "long",
                    "post_url_date_format": "yyyy/MM/dd",
                    "post_url_format": "{date}/{slug}",
                    "pagination_per_page": 10,
                    "categories_allowed": [
                        "daily",
                        "artificial-intelligence",
                        "philosophy",
                        "meetup",
                        "emergency",
                        "culture",
                        "psychology",
                        "neuroscience",
                        "open-source",
                        "social-engineering",
                    ],
                }
            },
            "tags",
            {"minify": {"minify_html": True}},
        ],
        "nav": [
            {"Home": "docs/index.md"},
            {"Blog": f"{DEFAULT_BLOG_DIR}/index.md"},
            {"Perfis": "profiles/index.md"},
            {"Sobre": "docs/about.md"},
        ],
        "markdown_extensions": [
            "abbr",
            "admonition",
            "attr_list",
            "def_list",
            "footnotes",
            "md_in_html",
            {"toc": {"permalink": True}},
            {"pymdownx.arithmatex": {"generic": True}},
            {"pymdownx.betterem": {"smart_enable": "all"}},
            "pymdownx.caret",
            "pymdownx.details",
            {
                "pymdownx.emoji": {
                    "emoji_index": "!!python/name:material.extensions.emoji.twemoji",
                    "emoji_generator": "!!python/name:material.extensions.emoji.to_svg",
                }
            },
            {
                "pymdownx.highlight": {
                    "anchor_linenums": True,
                    "line_spans": "__span",
                    "pygments_lang_class": True,
                }
            },
            "pymdownx.inlinehilite",
            "pymdownx.keys",
            "pymdownx.mark",
            "pymdownx.smartsymbols",
            {
                "pymdownx.superfences": {
                    "custom_fences": [
                        {
                            "name": "mermaid",
                            "class": "mermaid",
                            "format": "!!python/name:pymdownx.superfences.fence_code_format",
                        }
                    ]
                }
            },
            {"pymdownx.tabbed": {"alternate_style": True, "combine_header_slug": True}},
            {"pymdownx.tasklist": {"custom_checkbox": True}},
            "pymdownx.tilde",
        ],
        "extra": {"generator": False},
    }

    mkdocs_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

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
