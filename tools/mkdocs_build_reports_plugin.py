"""MkDocs plugin that builds newsletter report indexes before rendering docs."""

from __future__ import annotations

from mkdocs.plugins import BasePlugin

from .build_reports import build_reports


class BuildReportsPlugin(BasePlugin):
    """Ensure aggregated report pages exist ahead of the MkDocs build."""

    def on_pre_build(self, config) -> None:  # type: ignore[override]
        build_reports()


plugin = BuildReportsPlugin()
