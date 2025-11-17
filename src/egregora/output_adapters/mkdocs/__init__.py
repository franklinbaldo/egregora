"""MkDocs output adapter package."""

from egregora.output_adapters.mkdocs.adapter import (
    DEFAULT_BLOG_DIR,
    DEFAULT_DOCS_DIR,
    MEDIA_DIR_NAME,
    PROFILES_DIR_NAME,
    MkDocsAdapter,
    MkDocsUrlConvention,
    SitePaths,
    find_mkdocs_file,
    load_mkdocs_config,
    resolve_site_paths,
    secure_path_join,
)

__all__ = [
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    "MkDocsAdapter",
    "MkDocsUrlConvention",
    "SitePaths",
    "find_mkdocs_file",
    "load_mkdocs_config",
    "resolve_site_paths",
    "secure_path_join",
]
