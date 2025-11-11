"""Site scaffolding utilities for Egregora sites.

MODERN (Phase N): Refactored to use OutputFormat abstraction.
- MkDocs-specific logic moved to MkDocsOutputFormat.scaffold_site()
- This module now provides thin compatibility wrappers
- New code should use OutputFormat directly via create_output_format()
"""

import logging
from pathlib import Path

from egregora.config.site import resolve_site_paths
from egregora.rendering import create_output_format

logger = logging.getLogger(__name__)


def ensure_mkdocs_project(site_root: Path) -> tuple[Path, bool]:
    """Ensure site_root contains an MkDocs configuration.

    MODERN: This is a compatibility wrapper. New code should use:
        output_format = create_output_format(site_root, format_type="mkdocs")
        mkdocs_path, created = output_format.scaffold_site(site_root, site_name)

    Args:
        site_root: Root directory for the site

    Returns:
        tuple of (docs_dir, was_created)
        - docs_dir: Directory where documentation content should be written
        - was_created: True if new site was created, False if existed

    """
    # Use OutputFormat abstraction
    site_root = site_root.expanduser().resolve()
    site_name = site_root.name or "Egregora Archive"

    # Create and initialize MkDocs output format
    output_format = create_output_format(site_root, format_type="mkdocs")

    # Scaffold the site (idempotent - returns False if already exists)
    _mkdocs_path, created = output_format.scaffold_site(site_root, site_name)

    # Return docs_dir for backward compatibility
    site_paths = resolve_site_paths(site_root)
    docs_dir = site_paths.docs_dir
    docs_dir.mkdir(parents=True, exist_ok=True)

    return (docs_dir, created)



__all__ = ["ensure_mkdocs_project"]
