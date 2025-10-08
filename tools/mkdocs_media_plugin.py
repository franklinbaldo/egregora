"""MkDocs plugin to publish per-group media directories."""

from __future__ import annotations

import shutil
from pathlib import Path

from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin


class MediaFilesPlugin(BasePlugin):
    """Collect group media folders under ``data/posts`` for publication."""

    config_scheme = (
        ("source_dir", config_options.Type(str, default="data/posts")),
        ("target_dir", config_options.Type(str, default="media")),
    )

    def on_post_build(self, config) -> None:  # type: ignore[override]
        source_root = Path(self.config["source_dir"])
        if not source_root.exists():
            return

        target_root = Path(config["site_dir"]) / self.config["target_dir"]
        if target_root.exists():
            shutil.rmtree(target_root)

        for slug, media_dir in self._iter_media_directories(source_root):
            destination = target_root / slug
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(media_dir, destination)

    def on_serve(self, server, config, builder):  # type: ignore[override]
        source_root = Path(self.config["source_dir"])
        if source_root.exists():
            server.watch(str(source_root), builder)
        return server

    def _iter_media_directories(self, source_root: Path) -> list[tuple[str, Path]]:
        directories: list[tuple[str, Path]] = []
        for group_dir in sorted(source_root.iterdir()):
            if not group_dir.is_dir():
                continue
            media_dir = group_dir / "media"
            if media_dir.is_dir():
                directories.append((group_dir.name, media_dir))
        return directories


def on_config(config):
    """Keep MkDocs from trying to instantiate without using the plugin name."""
    return config


plugin = MediaFilesPlugin()
