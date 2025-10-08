"""MkDocs plugin that builds post indexes before rendering docs."""

from __future__ import annotations

from mkdocs.plugins import BasePlugin

from .build_posts import build_posts


class BuildPostsPlugin(BasePlugin):
    """Ensure aggregated post pages exist ahead of the MkDocs build."""

    def on_pre_build(self, config) -> None:  # type: ignore[override]
        build_posts()


plugin = BuildPostsPlugin()
