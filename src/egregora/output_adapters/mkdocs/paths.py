"""Path helpers for MkDocs output sites."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


__all__ = [
    "compute_site_prefix",
    "derive_mkdocs_paths",
]


def derive_mkdocs_paths(site_root: Path, *, config: Any | None = None) -> dict[str, Path | str | None]:  # noqa: C901
    """Derive MkDocs paths from configuration settings.

    This is a simplified alternative to load_site_paths() that:
    - Uses paths directly from EgregoraConfig settings
    - No filesystem searching or YAML parsing
    - Returns a dictionary instead of a dataclass
    - Simple, predictable path resolution

    Args:
        site_root: Root directory of the MkDocs site
        config: EgregoraConfig instance (required)

    Returns:
        Dictionary with path keys matching SitePaths attributes

    """
    if config is None:
        msg = "EgregoraConfig must be provided to derive_mkdocs_paths"
        raise ValueError(msg)

    resolved_root = site_root.expanduser().resolve()

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

    # Trust config/conventions for mkdocs.yml location
    # Egregora V3 standard: .egregora/mkdocs.yml
    preferred_path = egregora_dir / "mkdocs.yml"
    mkdocs_path = egregora_dir / "mkdocs.yml"

    docs_dir = resolve_path(paths_settings.docs_dir)

    def resolve_content_path(path_str: str) -> Path:
        """Resolve a content path relative to docs_dir when not absolute."""
        path_obj = Path(path_str)
        if path_obj.is_absolute():
            return path_obj.resolve()

        # Check if path is relative to docs_dir or site_root
        # Egregora V3 prefers relative to site_root if it's "docs/..."
        # But if it's "posts", it might mean "docs/posts" or "site/posts"

        # Simple rule: if it starts with docs_dir's name, treat as relative to root
        # Else treat as relative to docs_dir if inside docs_dir is desired?

        # If config explicitly nests under docs, use that.
        # Otherwise, try to infer based on structure.

        # For new sites (scaffolding), we want to enforce structure.
        # Default config usually implies nesting under docs/ for content.

        # If the path_str doesn't start with docs_dir name, and we are resolving content directories,
        # we generally expect them to be inside docs_dir for MkDocs to serve them.

        # However, resolve_path uses site_root.
        # Let's enforce docs_dir parentage for content if not already relative.

        try:
            # If path already includes docs_dir prefix (e.g. "docs/posts"), resolve from root
            if path_obj.parts[0] == docs_dir.name:
                return resolve_path(path_str)
        except IndexError:
            pass

        # Otherwise, assume it's a subdirectory of docs_dir
        return (docs_dir / path_obj).resolve()

    def normalize_path_str(path_value: str) -> str:
        return path_value.replace("\\", "/").strip("./")

    posts_dir = resolve_content_path(paths_settings.posts_dir)
    profiles_dir = resolve_content_path(paths_settings.profiles_dir)
    media_dir = resolve_content_path(paths_settings.media_dir)
    journal_setting = paths_settings.journal_dir
    posts_norm = normalize_path_str(paths_settings.posts_dir)
    journal_norm = normalize_path_str(journal_setting)
    legacy_norm = f"{posts_norm}/journal".strip("./")
    if journal_norm == legacy_norm:
        journal_setting = "journal"
    journal_dir = resolve_content_path(journal_setting)

    try:
        if not posts_dir.is_relative_to(docs_dir):
             # Try resolving against docs_dir instead (recovery for "sibling" misconfiguration)
             possible_posts = (docs_dir / paths_settings.posts_dir).resolve()
             if possible_posts != posts_dir:
                 posts_dir = possible_posts

        blog_relative = posts_dir.relative_to(docs_dir).as_posix()
    except ValueError:
        # Fallback: if we can't make it relative, assume it's just the name
        blog_relative = paths_settings.posts_dir

    return {
        "site_root": resolved_root,
        "mkdocs_path": mkdocs_path,
        "egregora_dir": egregora_dir,
        "config_path": egregora_dir / "config.yml",
        "mkdocs_config_path": preferred_path,
        "prompts_dir": resolve_path(paths_settings.prompts_dir),
        "rag_dir": resolve_path(paths_settings.rag_dir),
        "cache_dir": resolve_path(paths_settings.cache_dir),
        "docs_dir": docs_dir,
        "blog_dir": blog_relative,
        "posts_dir": posts_dir,
        "profiles_dir": profiles_dir,
        "media_dir": media_dir,
        "journal_dir": journal_dir,
        "rankings_dir": egregora_dir / "rankings",
        "enriched_dir": egregora_dir / "enriched",
    }


def compute_site_prefix(site_root: Path, docs_dir: Path) -> str:
    """Return docs_dir relative to site_root for URL generation."""
    try:
        docs_dir.relative_to(site_root)
    except ValueError:
        return ""

    # MkDocs serves content from the docs_dir as the site root; the docs_dir
    # itself should not appear in canonical URLs. Returning an empty prefix
    # keeps generated URLs aligned with MkDocs' served paths while still
    # allowing callers to validate the docs_dir relationship to site_root.
    return ""
