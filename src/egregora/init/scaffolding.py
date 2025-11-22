"""Site scaffolding utilities for Egregora sites.

ISP-COMPLIANT (2025-11-22): Uses SiteScaffolder protocol for initialization.
- MkDocs-specific logic in MkDocsAdapter.scaffold_site()
- This module provides thin compatibility wrappers
- New code should use SiteScaffolder directly via create_output_format()
"""

import logging
from pathlib import Path
from typing import cast

from egregora.data_primitives.protocols import SiteScaffolder
from egregora.output_adapters import create_output_format
from egregora.output_adapters.base import SiteScaffolder
from egregora.output_adapters.mkdocs import derive_mkdocs_paths

logger = logging.getLogger(__name__)


def ensure_mkdocs_project(site_root: Path, site_name: str | None = None) -> tuple[Path, bool]:
    """Ensure site_root contains an MkDocs configuration.

    ISP-COMPLIANT: Uses SiteScaffolder protocol for initialization.

    New code should use:
        scaffolder: SiteScaffolder = create_output_format(site_root, format_type="mkdocs")
        mkdocs_path, created = scaffolder.scaffold_site(site_root, site_name)

    Args:
        site_root: Root directory for the site
        site_name: Name for the site (defaults to directory name)

    Returns:
        tuple of (docs_dir, was_created)
        - docs_dir: Directory where documentation content should be written
        - was_created: True if new site was created, False if existed

    """
    # Use SiteScaffolder abstraction (MkDocsAdapter implements both OutputSink and SiteScaffolder)
    site_root = site_root.expanduser().resolve()
    if site_name is None:
        site_name = site_root.name or "Egregora Archive"

    # Create MkDocs adapter (implements SiteScaffolder protocol)
    scaffolder = cast("SiteScaffolder", create_output_format(site_root, format_type="mkdocs"))

    # Scaffold the site (idempotent - returns False if already exists)
    _mkdocs_path, created = scaffolder.scaffold_site(site_root, site_name)

    # Return docs_dir for backward compatibility
    site_paths = derive_mkdocs_paths(site_root)
    docs_dir = site_paths["docs_dir"]
    docs_dir.mkdir(parents=True, exist_ok=True)

    return (docs_dir, created)


__all__ = ["ensure_mkdocs_project"]
