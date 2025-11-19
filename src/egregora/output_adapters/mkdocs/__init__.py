"""MkDocs output adapter package.

CONSOLIDATED (2025-11-19): Removed individual constant exports.
Use EgregoraConfig().paths for directory configuration instead:
    - config.paths.docs_dir (was DEFAULT_DOCS_DIR)
    - config.paths.posts_dir (was DEFAULT_BLOG_DIR)
    - config.paths.profiles_dir (was PROFILES_DIR_NAME)
    - config.paths.media_dir (was MEDIA_DIR_NAME)
"""

from egregora.config.site import (
    SitePaths,
    configured_mkdocs_path,
    find_mkdocs_file,
    load_mkdocs_config,
    resolve_site_paths,
)
from egregora.output_adapters.mkdocs.adapter import (
    MkDocsAdapter,
    MkDocsUrlConvention,
    secure_path_join,
)

__all__ = [
    "MkDocsAdapter",
    "MkDocsUrlConvention",
    "SitePaths",
    "configured_mkdocs_path",
    "find_mkdocs_file",
    "load_mkdocs_config",
    "resolve_site_paths",
    "secure_path_join",
]
