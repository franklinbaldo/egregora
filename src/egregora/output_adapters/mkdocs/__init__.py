"""MkDocs output adapter package."""

from .adapter import (
    MkDocsEnrichmentStorage,
    MkDocsFilesystemAdapter,
    MkDocsJournalStorage,
    MkDocsOutputAdapter,
    MkDocsPostStorage,
    MkDocsProfileStorage,
    SitePaths,
    find_mkdocs_file,
    load_mkdocs_config,
    resolve_site_paths,
    secure_path_join,
)
from .url_convention import LegacyMkDocsUrlConvention

__all__ = [
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
