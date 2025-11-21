"""Path helpers for MkDocs output sites."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

# Legacy constants for backward compatibility
DEFAULT_DOCS_DIR = "docs"
DEFAULT_BLOG_DIR = "."
PROFILES_DIR_NAME = "profiles"
MEDIA_DIR_NAME = "media"


logger = logging.getLogger(__name__)


__all__ = [
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    "compute_site_prefix",
    "derive_mkdocs_paths",
]


def derive_mkdocs_paths(site_root: Path, *, config: Any | None = None) -> dict[str, Path | str | None]:
    """Derive MkDocs paths from configuration settings.

    This is a simplified alternative to load_site_paths() that:
    - Uses paths directly from EgregoraConfig settings
    - No filesystem searching or YAML parsing
    - Returns a dictionary instead of a dataclass
    - Simple, predictable path resolution

    Args:
        site_root: Root directory of the MkDocs site
        config: EgregoraConfig instance (optional, loads from site_root if not provided)

    Returns:
        Dictionary with path keys matching SitePaths attributes

    Example:
        >>> from egregora.config import load_egregora_config
        >>> config = load_egregora_config(Path("."))
        >>> paths = derive_mkdocs_paths(Path("."), config=config)
        >>> docs_dir = paths["docs_dir"]
        >>> posts_dir = paths["posts_dir"]

    """
    resolved_root = site_root.expanduser().resolve()

    # Load config if not provided
    if config is None:
        from egregora.config import load_egregora_config  # noqa: PLC0415

        config = load_egregora_config(resolved_root)

    # Resolve all paths from config settings (relative to site_root)
    def resolve_path(path_str: str) -> Path:
        """Resolve a path string relative to site_root."""
        path = Path(path_str)
        if path.is_absolute():
            return path.resolve()
        return (resolved_root / path).resolve()

    # Get paths from config settings
    paths_settings = config.paths
    egregora_dir = resolve_path(paths_settings.egregora_dir)

    # Check for mkdocs.yml (for mkdocs-material compatibility)
    mkdocs_path: Path | None = None
    preferred_path = egregora_dir / "mkdocs.yml"
    legacy_path = resolved_root / "mkdocs.yml"

    if preferred_path.exists():
        mkdocs_path = preferred_path
    elif legacy_path.exists():
        mkdocs_path = legacy_path

    # Resolve all paths from settings (no discovery logic)
    return {
        "site_root": resolved_root,
        "mkdocs_path": mkdocs_path,
        "egregora_dir": egregora_dir,
        "config_path": egregora_dir / "config.yml",
        "mkdocs_config_path": preferred_path,
        "prompts_dir": resolve_path(paths_settings.prompts_dir),
        "rag_dir": resolve_path(paths_settings.rag_dir),
        "cache_dir": resolve_path(paths_settings.cache_dir),
        "docs_dir": resolve_path(paths_settings.docs_dir),
        "blog_dir": paths_settings.posts_dir,  # Keep as string for compatibility
        "posts_dir": resolve_path(paths_settings.posts_dir),
        "profiles_dir": resolve_path(paths_settings.profiles_dir),
        "media_dir": resolve_path(paths_settings.media_dir),
        "rankings_dir": egregora_dir / "rankings",
        "enriched_dir": egregora_dir / "enriched",
    }


def compute_site_prefix(site_root: Path, docs_dir: Path) -> str:
    """Return docs_dir relative to site_root for URL generation."""
    try:
        relative = docs_dir.relative_to(site_root)
    except ValueError:
        return ""

    rel_str = relative.as_posix().strip("/")
    if rel_str in {"", "."}:
        return ""
    return rel_str
