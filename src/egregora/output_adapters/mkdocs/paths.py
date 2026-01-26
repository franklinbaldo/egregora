"""Path helpers for MkDocs output sites."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from egregora.config import load_egregora_config

__all__ = ["MkDocsPaths"]


class MkDocsPaths:
    """Resolved MkDocs paths configuration (Config Over Code)."""

    def __init__(self, site_root: Path, *, config: Any | None = None, site: str | None = None) -> None:
        self.site_root = site_root.expanduser().resolve()

        if config is None:
            config = load_egregora_config(self.site_root, site=site)

        self.config = config
        p = config.paths

        self.egregora_dir = (self.site_root / p.egregora_dir).resolve()
        self.config_path = self.site_root / ".egregora.toml"

        # Content content
        self.docs_dir = (self.site_root / p.docs_dir).resolve()
        self.posts_dir = (self.site_root / p.posts_dir).resolve()
        self.profiles_dir = (self.site_root / p.profiles_dir).resolve()
        self.media_dir = (self.site_root / p.media_dir).resolve()
        self.journal_dir = (self.site_root / p.journal_dir).resolve()

        # Internals
        self.prompts_dir = (self.site_root / p.prompts_dir).resolve()
        self.rag_dir = (self.site_root / p.rag_dir).resolve()
        self.cache_dir = (self.site_root / p.cache_dir).resolve()
        self.rankings_dir = (self.egregora_dir / "rankings").resolve()
        self.enriched_dir = (self.egregora_dir / "enriched").resolve()

    # MkDocs-specific Helpers

    @property
    def mkdocs_path(self) -> Path:
        """Locate the active mkdocs.yml file.

        Uses config.output.adapters[0].config_path if set,
        otherwise falls back to .egregora/mkdocs.yml or root mkdocs.yml.
        """
        # Check if config specifies a path via the adapter registry
        adapters = getattr(self.config.output, "adapters", [])
        if adapters:
            adapter_config_path = adapters[0].config_path
            if adapter_config_path:
                return (self.site_root / adapter_config_path).resolve()

        return self.mkdocs_config_path

    @property
    def mkdocs_config_path(self) -> Path:
        """Preferred location for creating new mkdocs.yml."""
        return self.egregora_dir / "mkdocs.yml"

    @property
    def blog_dir(self) -> str:
        """Return the blog path relative to docs_dir, or empty string."""
        if self.posts_dir.is_relative_to(self.docs_dir):
            return self.posts_dir.relative_to(self.docs_dir).as_posix()
        return ""

    @property
    def blog_root_dir(self) -> Path:
        """Alias for posts_dir for clarity in some contexts."""
        return self.posts_dir

    @property
    def docs_prefix(self) -> str:
        """Return docs_dir relative to site_root for URL generation."""
        if self.docs_dir.is_relative_to(self.site_root):
            return self.docs_dir.relative_to(self.site_root).as_posix()
        return ""

    # Dictionary compatibility for simpler migration if needed (optional)
    def to_dict(self) -> dict[str, Any]:
        return {
            k: getattr(self, k) for k in dir(self) if not k.startswith("_") and not callable(getattr(self, k))
        }
