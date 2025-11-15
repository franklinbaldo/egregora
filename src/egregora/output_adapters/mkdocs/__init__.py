"""MkDocs output adapter package."""

from egregora.output_adapters.mkdocs.adapter import (
    DEFAULT_BLOG_DIR,
    DEFAULT_DOCS_DIR,
    MEDIA_DIR_NAME,
    PROFILES_DIR_NAME,
    MkDocsAdapter,
    SitePaths,
    find_mkdocs_file,
    load_mkdocs_config,
    resolve_site_paths,
    secure_path_join,
)
from egregora.output_adapters.mkdocs.url_convention import (
    LegacyMkDocsUrlConvention,
)

__all__ = [
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    "LegacyMkDocsUrlConvention",
    "MkDocsEnrichmentStorage",
    "MkDocsFilesystemAdapter",
    "MkDocsJournalStorage",
    "MkDocsOutputAdapter",
    "MkDocsPostStorage",
    "MkDocsProfileStorage",
    "SitePaths",
    "find_mkdocs_file",
    "load_mkdocs_config",
    "resolve_site_paths",
    "secure_path_join",
]
