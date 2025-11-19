"""Utilities for reading MkDocs configuration and deriving site paths."""

from __future__ import annotations

import logging
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import ValidationError

from egregora.config.settings import EgregoraConfig
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
    MODERN (Regression Fix): Content at root level (not in docs/).
    - .egregora/config.yml - Configuration
    - .egregora/mkdocs.yml - MkDocs configuration
    - .egregora/prompts/ - Custom prompt overrides
    - .egregora/rag/ - Vector store data
    - .egregora/.cache/ - Ephemeral cache
    - media/ - Media files at root
    - profiles/ - Author profiles at root
    - posts/ - Blog posts at root
    """

    site_root: Path
    mkdocs_path: Path | None

    # Egregora directories (.egregora/)
    egregora_dir: Path
    config_path: Path
    mkdocs_config_path: Path  # Configured mkdocs.yml path
    prompts_dir: Path
    rag_dir: Path
    cache_dir: Path

    # Content directories (at root, not in docs/)
    docs_dir: Path  # For MkDocs compatibility, points to site_root
    blog_dir: str
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path
    rankings_dir: Path
    enriched_dir: Path


def _resolve_relative_path(site_root: Path, path_value: str | Path) -> Path:
    """Resolve a potentially relative path against the site root."""
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (site_root / candidate).resolve()


def load_config_for_paths(site_root: Path) -> EgregoraConfig:
    """Load config without creating files (safe for path resolution)."""
    config_path = site_root / ".egregora" / "config.yml"
    if not config_path.exists():
        return EgregoraConfig()

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.debug("Failed to read config at %s: %s", config_path, exc)
        return EgregoraConfig()

    try:
        return EgregoraConfig(**data)
    except ValidationError as exc:
        logger.debug("Validation failed for %s: %s", config_path, exc)
        return EgregoraConfig()


def configured_mkdocs_path(
    start: Annotated[Path, "Site root for mkdocs path resolution"],
    config: EgregoraConfig | None = None,
) -> Annotated[Path, "Configured mkdocs.yml path (may not exist)"]:
    """Return mkdocs.yml path from ``.egregora/config.yml`` without searching.

    Args:
        start: Site root directory
        config: Optional preloaded ``EgregoraConfig``. When omitted, the config
            is loaded from ``start/.egregora/config.yml``.

    """
    site_root = start.expanduser().resolve()
    config_model = config or load_config_for_paths(site_root)
    configured_path = config_model.output.mkdocs_config_path or ".egregora/mkdocs.yml"
    return _resolve_relative_path(site_root, configured_path)


def find_mkdocs_file(
    start: Annotated[Path, "The starting directory for the upward search"],
) -> Annotated[Path | None, "The path to mkdocs.yml, or None if not found"]:
    """Deprecated: use :func:`configured_mkdocs_path` instead.

    This function previously searched parent directories for ``mkdocs.yml``.
    It now resolves the configured path from ``.egregora/config.yml`` and does
    not perform any filesystem search.
    """
    warnings.warn(
        "find_mkdocs_file() is deprecated. Use configured_mkdocs_path() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    mkdocs_path = configured_mkdocs_path(start)
    if mkdocs_path.exists():
        return mkdocs_path
    legacy_path = start.expanduser().resolve() / "mkdocs.yml"
    return legacy_path if legacy_path.exists() else None


def _read_mkdocs_config(mkdocs_path: Path) -> dict[str, Any]:
    """Read mkdocs.yml content using the tolerant YAML loader."""
    try:
        return yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse mkdocs.yml at %s: %s", mkdocs_path, exc)
        return {}


def load_mkdocs_config(
    start: Annotated[Path, "Site root for resolving mkdocs.yml"],
    config: EgregoraConfig | None = None,
) -> tuple[
    Annotated[dict[str, Any], "The loaded mkdocs.yml as a dictionary"],
    Annotated[Path | None, "The path to the found mkdocs.yml, or None"],
]:
    """Deprecated: load mkdocs.yml from the configured path.

    This function now resolves ``mkdocs.yml`` using :func:`configured_mkdocs_path`
    without performing directory searches.
    """
    warnings.warn(
        "load_mkdocs_config() is deprecated. Use resolve_site_paths() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    site_root = start.expanduser().resolve()
    mkdocs_path = configured_mkdocs_path(site_root, config)
    if not mkdocs_path.exists():
        logger.debug("mkdocs.yml not found at configured path %s", mkdocs_path)
        return ({}, None)

    return (_read_mkdocs_config(mkdocs_path), mkdocs_path)


def _resolve_docs_dir(mkdocs_path: Path | None, config: dict[str, Any], site_root: Path) -> Path:
    """Return the absolute docs directory based on MkDocs config.

    Args:
        mkdocs_path: Path to mkdocs.yml (used as base for relative paths)
        config: Parsed mkdocs.yml dictionary

    Returns:
        Absolute path to docs directory

    Note:
        docs_dir is resolved relative to mkdocs.yml location (same as MkDocs behavior)

    """
    docs_setting = config.get("docs_dir", DEFAULT_DOCS_DIR)
    docs_setting = "." if docs_setting in ("./", "") else docs_setting

    # If mkdocs_path not provided, fall back to site_root (no search)
    base_dir = mkdocs_path.parent if mkdocs_path else site_root

    if docs_setting in (".", None):
        return base_dir
    docs_path = Path(str(docs_setting))
    if docs_path.is_absolute():
        return docs_path
    # CRITICAL: Resolve relative to mkdocs.yml location, not site_root
    return (base_dir / docs_path).resolve()


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


def resolve_site_paths(
    start: Annotated[Path, "The starting directory for path resolution"],
    config: EgregoraConfig | None = None,
) -> SitePaths:
    """Resolve all important directories for the site.

    SIMPLIFIED (Alpha): All egregora data in .egregora/ directory.
    MODERN (Regression Fix): Content at root level (not in docs/).
    MODERN (Phase N): Respects output.mkdocs_config_path from .egregora/config.yml
    """
    site_root = start.expanduser().resolve()
    config_model = config or load_config_for_paths(site_root)
    mkdocs_path = configured_mkdocs_path(site_root, config_model)
    _config = _read_mkdocs_config(mkdocs_path) if mkdocs_path.exists() else {}

    # .egregora/ structure (new)
    egregora_dir = _resolve_relative_path(site_root, config_model.paths.egregora_dir)
    config_path = egregora_dir / "config.yml"
    mkdocs_config_path = mkdocs_path
    prompts_dir = _resolve_relative_path(site_root, config_model.paths.prompts_dir)
    rag_dir = _resolve_relative_path(site_root, config_model.paths.rag_dir)
    cache_dir = _resolve_relative_path(site_root, config_model.paths.cache_dir)

    # Content directories - resolve docs_dir from mkdocs.yml
    # CRITICAL: docs_dir is resolved relative to mkdocs.yml location (same as MkDocs)
    # Example: .egregora/mkdocs.yml with docs_dir: ".." → resolves to site root
    docs_dir = _resolve_docs_dir(mkdocs_path, _config, site_root)
    blog_dir = DEFAULT_BLOG_DIR
    posts_dir = _resolve_relative_path(site_root, config_model.paths.posts_dir)
    profiles_dir = _resolve_relative_path(site_root, config_model.paths.profiles_dir)
    media_dir = _resolve_relative_path(site_root, config_model.paths.media_dir)
    rankings_dir = (site_root / "rankings").resolve()
    enriched_dir = (site_root / "enriched").resolve()

    return SitePaths(
        site_root=site_root,
        mkdocs_path=mkdocs_path,
        # .egregora/ paths
        egregora_dir=egregora_dir,
        config_path=config_path,
        mkdocs_config_path=mkdocs_config_path,
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
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    "SitePaths",
    "configured_mkdocs_path",
    "find_mkdocs_file",
    "load_config_for_paths",
    "load_mkdocs_config",
    "resolve_site_paths",
]
