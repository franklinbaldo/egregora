"""Utilities for preparing MkDocs-compatible output folders."""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_SITE_NAME = "Egregora Archive"


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


def _create_default_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Create a minimal MkDocs configuration and return the docs directory path."""

    site_name = site_root.name or DEFAULT_SITE_NAME
    config = {
        "site_name": site_name,
        "docs_dir": ".",
        "theme": {"name": "material"},
    }
    mkdocs_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return site_root


__all__ = ["ensure_mkdocs_project"]
