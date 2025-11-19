"""Path helpers for MkDocs output sites."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Legacy constants for backward compatibility
DEFAULT_DOCS_DIR = "docs"
DEFAULT_BLOG_DIR = "."
PROFILES_DIR_NAME = "profiles"
MEDIA_DIR_NAME = "media"


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SitePaths:
    """Resolved paths for an Egregora MkDocs site."""

    site_root: Path
    mkdocs_path: Path | None

    # Egregora directories (.egregora/)
    egregora_dir: Path
    config_path: Path
    mkdocs_config_path: Path
    prompts_dir: Path
    rag_dir: Path
    cache_dir: Path

    # Content directories
    docs_dir: Path
    blog_dir: str
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path
    rankings_dir: Path
    enriched_dir: Path


def load_site_paths(site_root: Path) -> SitePaths:
    """Resolve MkDocs site structure from the filesystem and mkdocs.yml."""
    resolved_root = site_root.expanduser().resolve()
    config_path = resolved_root / ".egregora" / "config.yml"
    config_data = _load_config_dict(config_path)
    path_overrides = _extract_path_overrides(resolved_root, config_data)

    preferred_mkdocs_path = _preferred_mkdocs_config_path(resolved_root, config_data)
    mkdocs_path = _discover_mkdocs_config(resolved_root, preferred_mkdocs_path, config_data)
    docs_dir, blog_dir = _resolve_docs_and_blog_dirs(resolved_root, mkdocs_path)
    docs_dir = path_overrides.get("docs_dir", docs_dir)

    posts_dir = path_overrides.get("posts_dir") or _resolve_relative(docs_dir, blog_dir)
    profiles_dir = path_overrides.get("profiles_dir") or _resolve_relative(docs_dir, PROFILES_DIR_NAME)
    media_dir = path_overrides.get("media_dir") or _resolve_relative(docs_dir, MEDIA_DIR_NAME)

    egregora_dir = resolved_root / ".egregora"
    return SitePaths(
        site_root=resolved_root,
        mkdocs_path=mkdocs_path,
        egregora_dir=egregora_dir,
        config_path=config_path,
        mkdocs_config_path=preferred_mkdocs_path,
        prompts_dir=path_overrides.get("prompts_dir") or (egregora_dir / "prompts"),
        rag_dir=path_overrides.get("rag_dir") or (egregora_dir / "rag"),
        cache_dir=path_overrides.get("cache_dir") or (egregora_dir / ".cache"),
        docs_dir=docs_dir,
        blog_dir=blog_dir,
        posts_dir=posts_dir,
        profiles_dir=profiles_dir,
        media_dir=media_dir,
        rankings_dir=egregora_dir / "rankings",
        enriched_dir=egregora_dir / "enriched",
    )


def _load_config_dict(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to read %s: %s", config_path, exc)
        return {}
    if isinstance(loaded, dict):
        return loaded
    logger.warning("Unexpected data in %s; expected mapping, got %s", config_path, type(loaded).__name__)
    return {}


def _extract_path_overrides(site_root: Path, config_data: dict[str, Any]) -> dict[str, Path]:
    raw_paths = config_data.get("paths")
    if not isinstance(raw_paths, dict):
        return {}

    overrides: dict[str, Path] = {}
    allowed_keys = {
        "docs_dir",
        "posts_dir",
        "profiles_dir",
        "media_dir",
        "prompts_dir",
        "rag_dir",
        "cache_dir",
    }
    for key in allowed_keys:
        value = raw_paths.get(key)
        if isinstance(value, str) and value.strip():
            overrides[key] = _resolve_site_relative(site_root, value)
    return overrides


def _preferred_mkdocs_config_path(site_root: Path, config_data: dict[str, Any]) -> Path:
    output_settings = config_data.get("output") or {}
    custom_path = output_settings.get("mkdocs_config_path")
    if isinstance(custom_path, str) and custom_path:
        candidate = Path(custom_path)
        if not candidate.is_absolute():
            candidate = site_root / candidate
        return candidate.resolve()
    return (site_root / ".egregora" / "mkdocs.yml").resolve()


def _discover_mkdocs_config(
    site_root: Path, preferred_path: Path, config_data: dict[str, Any]
) -> Path | None:
    candidates: list[Path] = []
    custom = config_data.get("output", {}).get("mkdocs_config_path")
    if isinstance(custom, str) and custom:
        custom_path = Path(custom)
        if not custom_path.is_absolute():
            custom_path = site_root / custom_path
        candidates.append(custom_path.resolve())
    candidates.append(preferred_path)
    candidates.append((site_root / "mkdocs.yml").resolve())

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def _resolve_docs_and_blog_dirs(site_root: Path, mkdocs_path: Path | None) -> tuple[Path, str]:
    if not mkdocs_path:
        return site_root, "posts"

    try:
        mkdocs_data = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to parse mkdocs config at %s: %s", mkdocs_path, exc)
        mkdocs_data = {}

    docs_value = mkdocs_data.get("docs_dir", DEFAULT_DOCS_DIR)
    docs_dir = _resolve_path_relative_to_config(mkdocs_path, docs_value)

    blog_dir = "posts"
    for plugin in mkdocs_data.get("plugins", []):
        if isinstance(plugin, dict) and "blog" in plugin:
            blog_cfg = plugin.get("blog") or {}
            if isinstance(blog_cfg, dict):
                blog_dir = blog_cfg.get("blog_dir", blog_dir) or blog_dir
            break

    return docs_dir, blog_dir


def _resolve_path_relative_to_config(config_file: Path, raw_value: str | Path) -> Path:
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (config_file.parent / candidate).resolve()


def _resolve_relative(base_dir: Path, relative_subdir: str | Path) -> Path:
    if not relative_subdir or str(relative_subdir) in {".", ""}:
        return base_dir
    return (base_dir / Path(relative_subdir)).resolve()


def _resolve_site_relative(site_root: Path, raw_value: str | Path) -> Path:
    candidate = Path(raw_value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (site_root / candidate).resolve()


__all__ = [
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    "SitePaths",
    "load_site_paths",
]
