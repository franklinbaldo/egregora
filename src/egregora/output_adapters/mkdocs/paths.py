"""Path constants and dataclass for MkDocs sites.

SIMPLIFIED (2025-11-19): Only contains SitePaths dataclass and constants.
Callers should read EgregoraConfig directly for path resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


__all__ = [
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    "SitePaths",
]
