"""Compat wrappers for MkDocs site path resolution.

The MkDocs path resolution logic now lives in
``egregora.output_adapters.mkdocs.paths`` so the output adapter remains the
single source of truth. This module re-exports the helpers to avoid breaking
existing imports.
"""

from egregora.output_adapters.mkdocs.paths import (
    DEFAULT_BLOG_DIR,
    DEFAULT_DOCS_DIR,
    MEDIA_DIR_NAME,
    PROFILES_DIR_NAME,
    SitePaths,
)

__all__ = [
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    "SitePaths",
]
