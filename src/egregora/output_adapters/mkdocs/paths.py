"""Path resolution helpers for MkDocs sites.

DETERMINISTIC (2025-11-19): All paths are resolved from EgregoraConfig.
No directory searching - paths come directly from configuration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)

# Legacy constants for backward compatibility
DEFAULT_DOCS_DIR = "docs"
DEFAULT_BLOG_DIR = "."
PROFILES_DIR_NAME = "profiles"
MEDIA_DIR_NAME = "media"


@dataclass(frozen=True, slots=True)
class SitePaths:
    """Resolved paths for an Egregora MkDocs site.

    All paths are derived from EgregoraConfig - no searching.
    """

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


def resolve_site_paths(site_root: Path, config: EgregoraConfig | None = None) -> SitePaths:
    """Resolve all site paths from EgregoraConfig.

    DETERMINISTIC: All paths come from config, no directory searching.

    Args:
        site_root: Root directory of the site
        config: Optional EgregoraConfig. If None, loads from site_root.

    Returns:
        SitePaths with all resolved absolute paths
    """
    site_root = site_root.expanduser().resolve()

    # Load config if not provided
    if config is None:
        from egregora.config.settings import load_egregora_config

        config = load_egregora_config(site_root)

    # Resolve all paths from config.paths
    egregora_dir = (site_root / config.paths.egregora_dir).resolve()
    config_path = egregora_dir / "config.yml"

    # MkDocs config path from output settings
    mkdocs_config_rel = config.output.mkdocs_config_path or ".egregora/mkdocs.yml"
    mkdocs_config_path = (site_root / mkdocs_config_rel).resolve()

    # Check if mkdocs.yml exists
    mkdocs_path = mkdocs_config_path if mkdocs_config_path.exists() else None

    # All other paths from config.paths
    prompts_dir = (site_root / config.paths.prompts_dir).resolve()
    rag_dir = (site_root / config.paths.rag_dir).resolve()
    cache_dir = (site_root / config.paths.cache_dir).resolve()
    docs_dir = (site_root / config.paths.docs_dir).resolve()
    posts_dir = (site_root / config.paths.posts_dir).resolve()
    profiles_dir = (site_root / config.paths.profiles_dir).resolve()
    media_dir = (site_root / config.paths.media_dir).resolve()

    # Fixed paths (not in config yet)
    rankings_dir = (site_root / "rankings").resolve()
    enriched_dir = (site_root / "enriched").resolve()

    return SitePaths(
        site_root=site_root,
        mkdocs_path=mkdocs_path,
        egregora_dir=egregora_dir,
        config_path=config_path,
        mkdocs_config_path=mkdocs_config_path,
        prompts_dir=prompts_dir,
        rag_dir=rag_dir,
        cache_dir=cache_dir,
        docs_dir=docs_dir,
        blog_dir=DEFAULT_BLOG_DIR,
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
    "resolve_site_paths",
]
