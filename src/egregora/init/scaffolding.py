"""Site scaffolding utilities for Egregora sites.

Modernized to use the ``SiteScaffolder`` interface instead of the broader
output sink abstraction. Scaffolding is handled by adapters that explicitly
support lifecycle management (currently MkDocs).
"""

import logging
from pathlib import Path

from egregora.data_primitives.protocols import SiteScaffolder
from egregora.output_adapters.mkdocs import MkDocsAdapter, derive_mkdocs_paths

logger = logging.getLogger(__name__)


def ensure_mkdocs_project(site_root: Path, site_name: str | None = None) -> tuple[Path, bool]:
    """Ensure site_root contains an MkDocs configuration.

    MODERN: This is a compatibility wrapper. New code should use:
        output_format = create_output_format(site_root, format_type="mkdocs")
        mkdocs_path, created = output_format.scaffold_site(site_root, site_name)

    Args:
        site_root: Root directory for the site
        site_name: Name for the site (defaults to directory name)

    Returns:
        tuple of (docs_dir, was_created)
        - docs_dir: Directory where documentation content should be written
        - was_created: True if new site was created, False if existed

    """
    # Use adapter that supports scaffolding explicitly
    site_root = site_root.expanduser().resolve()
    if site_name is None:
        site_name = site_root.name or "Egregora Archive"

    scaffolder: SiteScaffolder = MkDocsAdapter()
    existed_before = scaffolder.validate_structure(site_root)
    scaffolder.scaffold(site_root, {"site_name": site_name})
    created = not existed_before

    # Return docs_dir for backward compatibility
    site_paths = derive_mkdocs_paths(site_root)
    docs_dir = site_paths["docs_dir"]
    docs_dir.mkdir(parents=True, exist_ok=True)

    return (docs_dir, created)


__all__ = ["ensure_mkdocs_project"]
