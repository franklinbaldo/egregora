"""MkDocs plugin to expose the extracted media directory."""

from __future__ import annotations

import shutil
from pathlib import Path

from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin


class MediaFilesPlugin(BasePlugin):
    """Copy the repository ``media/`` directory into the built site."""

    config_scheme = (
        ("source_dir", config_options.Type(str, default="media")),
        ("target_dir", config_options.Type(str, default="media")),
    )

    def on_post_build(self, config) -> None:  # type: ignore[override]
        source = Path(self.config["source_dir"])
        if not source.exists():
            return

        target = Path(config["site_dir"]) / self.config["target_dir"]
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)

    def on_serve(self, server, config, builder):  # type: ignore[override]
        source = Path(self.config["source_dir"])
        if source.exists():
            server.watch(str(source), builder)
        return server


def on_config(config):
    """Keep MkDocs from trying to instantiate without using the plugin name."""
    return config


plugin = MediaFilesPlugin()
