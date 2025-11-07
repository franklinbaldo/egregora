"""Utilities for reading MkDocs configuration and deriving site paths."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import yaml

from egregora.constants import PluginType

logger = logging.getLogger(__name__)
DEFAULT_DOCS_DIR = "docs"
DEFAULT_BLOG_DIR = "."
PROFILES_DIR_NAME = "profiles"
MEDIA_DIR_NAME = "media"


class _ConfigLoader(yaml.SafeLoader):
    """YAML loader that tolerates MkDocs plugin tags."""


def _construct_python_name(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> str:
    """Return python/name tags as plain strings."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    return ""


def _construct_env(loader: yaml.SafeLoader, node: yaml.Node) -> str:
    """Handle MkDocs Material !ENV tags for environment variable substitution.

    !ENV expects either:
    - A string: !ENV VAR_NAME
    - A list: !ENV [VAR_NAME, "default_value"]
    """
    if isinstance(node, yaml.ScalarNode):
        var_name = loader.construct_scalar(node)
        return os.environ.get(var_name, "")
    if isinstance(node, yaml.SequenceNode):
        items = loader.construct_sequence(node)
        if not items:
            return ""
        var_name = items[0]
        default = items[1] if len(items) > 1 else ""
        return os.environ.get(var_name, default)
    return ""


_ConfigLoader.add_multi_constructor("tag:yaml.org,2002:python/name", _construct_python_name)
_ConfigLoader.add_constructor("!ENV", _construct_env)


@dataclass(frozen=True, slots=True)
class SitePaths:
    """Resolved paths for an Egregora MkDocs site.

    SIMPLIFIED (Alpha): All egregora data in .egregora/ directory.
    - .egregora/config.yml - Configuration
    - .egregora/prompts/ - Custom prompt overrides
    - .egregora/rag/ - Vector store data
    - .egregora/.cache/ - Ephemeral cache
    """

    site_root: Path
    mkdocs_path: Path | None

    # Egregora directories (.egregora/)
    egregora_dir: Path
    config_path: Path
    prompts_dir: Path
    rag_dir: Path
    cache_dir: Path

    # Content directories (docs/)
    docs_dir: Path
    blog_dir: str
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path
    rankings_dir: Path
    enriched_dir: Path


def find_mkdocs_file(
    start: Annotated[Path, "The starting directory for the upward search"],
) -> Annotated[Path | None, "The path to mkdocs.yml, or None if not found"]:
    """Search upward from ``start`` for ``mkdocs.yml``."""
    current = start.expanduser().resolve()
    for candidate in (current, *current.parents):
        mkdocs_path = candidate / "mkdocs.yml"
        if mkdocs_path.exists():
            return mkdocs_path
    return None


def load_mkdocs_config(
    start: Annotated[Path, "The starting directory to search for mkdocs.yml"],
) -> tuple[
    Annotated[dict[str, Any], "The loaded mkdocs.yml as a dictionary"],
    Annotated[Path | None, "The path to the found mkdocs.yml, or None"],
]:
    """Load ``mkdocs.yml`` as a dict, returning empty config when missing."""
    mkdocs_path = find_mkdocs_file(start)
    if not mkdocs_path:
        logger.debug("mkdocs.yml not found when starting from %s", start)
        return ({}, None)
    try:
        config = yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}  # noqa: S506 - trusted config file
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse mkdocs.yml at %s: %s", mkdocs_path, exc)
        config = {}
    return (config, mkdocs_path)


def _resolve_docs_dir(site_root: Path, config: dict[str, Any]) -> Path:
    """Return the absolute docs directory based on MkDocs config."""
    docs_setting = config.get("docs_dir", DEFAULT_DOCS_DIR)
    docs_setting = "." if docs_setting in ("./", "") else docs_setting
    if docs_setting in (".", None):
        return site_root
    docs_path = Path(str(docs_setting))
    if docs_path.is_absolute():
        return docs_path
    return (site_root / docs_path).resolve()


def _extract_blog_dir(config: dict[str, Any]) -> str | None:
    """Extract blog_dir from the blog plugin configuration."""
    plugins = config.get("plugins") or []
    for plugin in plugins:
        if isinstance(plugin, str):
            if plugin == PluginType.BLOG.value:
                return DEFAULT_BLOG_DIR
            continue
        if isinstance(plugin, dict) and PluginType.BLOG.value in plugin:
            blog_config = plugin.get(PluginType.BLOG.value) or {}
            return str(blog_config.get("blog_dir", DEFAULT_BLOG_DIR))
    return None


def resolve_site_paths(start: Annotated[Path, "The starting directory for path resolution"]) -> SitePaths:
    """Resolve all important directories for the site.

    SIMPLIFIED (Alpha): All egregora data in .egregora/ directory.
    """
    start = start.expanduser().resolve()
    config, mkdocs_path = load_mkdocs_config(start)
    site_root = mkdocs_path.parent if mkdocs_path else start

    # .egregora/ structure (new)
    egregora_dir = site_root / ".egregora"
    config_path = egregora_dir / "config.yml"
    prompts_dir = egregora_dir / "prompts"
    rag_dir = egregora_dir / "rag"
    cache_dir = egregora_dir / ".cache"

    # Content directories (docs/)
    docs_dir = _resolve_docs_dir(site_root, config)
    blog_dir = _extract_blog_dir(config) or DEFAULT_BLOG_DIR
    blog_path = Path(blog_dir)
    if blog_path.is_absolute():
        posts_dir = blog_path / "posts"
    else:
        posts_dir = (docs_dir / blog_path / "posts").resolve()
    profiles_dir = (docs_dir / PROFILES_DIR_NAME).resolve()
    media_dir = (docs_dir / MEDIA_DIR_NAME).resolve()
    rankings_dir = (site_root / "rankings").resolve()
    enriched_dir = (site_root / "enriched").resolve()

    return SitePaths(
        site_root=site_root,
        mkdocs_path=mkdocs_path,
        # .egregora/ paths
        egregora_dir=egregora_dir,
        config_path=config_path,
        prompts_dir=prompts_dir,
        rag_dir=rag_dir,
        cache_dir=cache_dir,
        # Content paths
        docs_dir=docs_dir,
        blog_dir=blog_dir,
        posts_dir=posts_dir,
        profiles_dir=profiles_dir,
        media_dir=media_dir,
        rankings_dir=rankings_dir,
        enriched_dir=enriched_dir,
    )


__all__ = [
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "SitePaths",
    "find_mkdocs_file",
    "load_mkdocs_config",
    "resolve_site_paths",
]
