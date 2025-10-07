"""MkDocs hook and plugin to expose the extracted media directory."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Tuple

from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin

DEFAULT_SOURCE_DIR = "data/media"
DEFAULT_TARGET_DIR = "media"
EXTRA_KEY = "media_files_plugin"


def _resolve_paths_from_extra(config) -> Tuple[Path, Path]:
    """Resolve media source/target directories from MkDocs extra config."""

    extra = getattr(config, "extra", {}) or {}
    extra_cfg = extra.get(EXTRA_KEY, {}) or {}

    source_dir = Path(extra_cfg.get("source_dir", DEFAULT_SOURCE_DIR))
    target_dir = Path(extra_cfg.get("target_dir", DEFAULT_TARGET_DIR))
    return source_dir, target_dir


def _copy_media_tree(source: Path, target: Path) -> None:
    """Copy media assets if the source directory exists."""

    if not source.exists():
        return

    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


class MediaFilesPlugin(BasePlugin):
    """Copy the repository ``data/media/`` directory into the built site."""

    config_scheme = (
        ("source_dir", config_options.Type(str, default=DEFAULT_SOURCE_DIR)),
        ("target_dir", config_options.Type(str, default=DEFAULT_TARGET_DIR)),
    )

    def on_post_build(self, config) -> None:  # type: ignore[override]
        source = Path(self.config["source_dir"])
        target = Path(config["site_dir"]) / self.config["target_dir"]
        _copy_media_tree(source, target)

    def on_serve(self, server, config, builder):  # type: ignore[override]
        source = Path(self.config["source_dir"])
        if source.exists():
            server.watch(str(source), builder)
        return server


def on_post_build(config) -> None:
    """Hook entry point used via ``hooks`` configuration."""

    source, target = _resolve_paths_from_extra(config)
    site_dir = Path(config["site_dir"])
    _copy_media_tree(source, site_dir / target)


def on_serve(server, config, builder):
    """Hook entry point to refresh media assets during ``mkdocs serve``."""

    source, _ = _resolve_paths_from_extra(config)
    if source.exists():
        server.watch(str(source), builder)
    return server


def on_config(config):
    """Keep MkDocs from trying to instantiate without using the plugin name."""

    return config


plugin = MediaFilesPlugin()
