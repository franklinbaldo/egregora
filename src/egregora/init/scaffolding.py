"""Site scaffolding utilities for Egregora sites.

MODERN (Phase N): Refactored to use OutputAdapter abstraction.
- MkDocs-specific logic moved to MkDocsOutputAdapter.scaffold_site()
- This module now provides thin compatibility wrappers
- New code should use OutputAdapter directly via create_output_format()
"""

import logging
from pathlib import Path
from typing import cast

from egregora.data_primitives.protocols import SiteScaffolder
from egregora.output_adapters import create_default_output_registry, create_output_sink
from egregora.output_adapters.mkdocs import MkDocsPaths

logger = logging.getLogger(__name__)


def ensure_mkdocs_project(site_root: Path, site_name: str | None = None) -> tuple[Path, bool]:
    """Ensure site_root contains an MkDocs configuration.

    MODERN: This is a compatibility wrapper. New code should use:
        output_format = create_output_sink(site_root, format_type="mkdocs")
        mkdocs_path, created = output_format.scaffold_site(site_root, site_name)

    Args:
        site_root: Root directory for the site
        site_name: Name for the site (defaults to directory name)

    Returns:
        tuple of (docs_dir, was_created)
        - docs_dir: Directory where documentation content should be written
        - was_created: True if new site was created, False if existed

    """
    # Use OutputAdapter abstraction
    site_root = site_root.expanduser().resolve()
    if site_name is None:
        site_name = site_root.name or "Egregora Archive"

    # Create and initialize MkDocs output format
    registry = create_default_output_registry()
    output_format = create_output_sink(site_root, format_type="mkdocs", registry=registry)

    if not isinstance(output_format, SiteScaffolder):
        logger.info("Output format %s does not support scaffolding", output_format)
        # Fallback for non-scaffolding adapters
        try:
            site_paths = MkDocsPaths(site_root)
            return (site_paths.docs_dir, False)
        except (ValueError, KeyError, OSError) as e:
            logger.debug("Failed to derive MkDocs paths, falling back to default: %s", e)
            return (site_root / "docs", False)

    # Cast to SiteScaffolder for type checking
    scaffolder = cast("SiteScaffolder", output_format)

    try:
        # Prefer specific implementation if available to get accurate 'created' status
        if hasattr(output_format, "scaffold_site"):
            _, created = output_format.scaffold_site(site_root, site_name)
        else:
            scaffolder.scaffold(site_root, {"site_name": site_name})
            # Generic scaffold doesn't return created status, assume True if no error
            created = True
    except Exception:
        logger.exception("Failed to scaffold site")
        raise

    # Return docs_dir for backward compatibility
    site_paths = MkDocsPaths(site_root)
    docs_dir = site_paths.docs_dir
    docs_dir.mkdir(parents=True, exist_ok=True)

    return (docs_dir, created)


__all__ = ["ensure_mkdocs_project"]
