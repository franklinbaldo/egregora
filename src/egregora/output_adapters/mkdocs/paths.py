"""Path helpers for MkDocs output sites."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from egregora.config import load_egregora_config

logger = logging.getLogger(__name__)


__all__ = [
    "compute_site_prefix",
    "derive_mkdocs_paths",
]


def _resolve_mkdocs_yml_path(
    resolved_root: Path, egregora_dir: Path, configured_path: str | None
) -> tuple[Path | None, Path]:
    """Find the mkdocs.yml file path."""

    def resolve_candidate(path_value: Path) -> Path:
        if path_value.is_absolute():
            return path_value
        return (resolved_root / path_value).resolve()

    configured = Path(configured_path) if configured_path else None
    preferred_path = resolve_candidate(configured or Path("mkdocs.yml"))

    root_path = (resolved_root / "mkdocs.yml").resolve()
    legacy_path = (egregora_dir / "mkdocs.yml").resolve()

    mkdocs_path: Path | None = None
    for candidate in [preferred_path, root_path, legacy_path]:
        if candidate.exists():
            mkdocs_path = candidate
            break

    return mkdocs_path, preferred_path


def _resolve_journal_dir(
    paths_settings: Any,
    resolve_content_path: Any,
) -> Path:
    """Resolve journal directory, handling legacy path normalization logic."""

    def normalize_path_str(path_value: str) -> str:
        return path_value.replace("\\", "/").strip("./")

    journal_setting = paths_settings.journal_dir
    posts_norm = normalize_path_str(paths_settings.posts_dir)
    journal_norm = normalize_path_str(journal_setting)
    legacy_norm = f"{posts_norm}/journal".strip("./")
    if journal_norm == legacy_norm:
        journal_setting = "journal"
    return resolve_content_path(journal_setting)


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

    """
    resolved_root = site_root.expanduser().resolve()

    # Load config if not provided
    if config is None:
        config = load_egregora_config(resolved_root)

    # Resolve all paths from config settings (relative to site_root)
    def resolve_path(path_str: str) -> Path:
        """Resolve a path string relative to site_root."""
        path = Path(path_str)
        if path.is_absolute():
            return path.resolve()
        return (resolved_root / path).resolve()

    paths_settings = config.paths
    egregora_dir = resolve_path(paths_settings.egregora_dir)
    mkdocs_path, preferred_path = _resolve_mkdocs_yml_path(
        resolved_root, egregora_dir, getattr(config.output, "mkdocs_config_path", None)
    )
    docs_dir = resolve_path(paths_settings.docs_dir)

    def resolve_content_path(path_str: str) -> Path:
        """Resolve a content path relative to docs_dir when not absolute."""
        path_obj = Path(path_str)
        if path_obj.is_absolute():
            return path_obj.resolve()

        candidate = (resolved_root / path_obj).resolve()
        try:
            candidate.relative_to(docs_dir)
        except ValueError:
            pass
        else:
            return candidate

        return (docs_dir / path_obj).resolve()

    # blog_root_dir is where blog artifacts go (e.g., docs/posts/)
    # posts_dir is where actual post files go (same as blog_root_dir)
    blog_root_dir = resolve_content_path(paths_settings.posts_dir)
    # Keep posts alongside the blog root to avoid nested posts/posts paths
    posts_dir = blog_root_dir
    profiles_dir = resolve_content_path(paths_settings.profiles_dir)
    media_dir = resolve_content_path(paths_settings.media_dir)
    journal_dir = _resolve_journal_dir(paths_settings, resolve_content_path)

    try:
        blog_relative = blog_root_dir.relative_to(docs_dir).as_posix()
    except ValueError as exc:  # pragma: no cover - enforced earlier
        msg = (
            "Posts directory must reside inside the MkDocs docs_dir. "
            f"docs_dir={docs_dir}, blog_root_dir={blog_root_dir}"
        )
        raise ValueError(msg) from exc

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
        "blog_root_dir": blog_root_dir,  # Where tags.md and blog artifacts go
        "posts_dir": posts_dir,  # Where actual post files go (posts/)
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
