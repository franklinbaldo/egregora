"""MkDocs macros for the demo site.

This module provides custom macros for the demo site, including
author data retrieval from profile markdown files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from mkdocs_macros.plugin import MacrosPlugin

logger = logging.getLogger(__name__)

# Number of parts expected when splitting frontmatter (---, content, ---)
FRONTMATTER_PARTS = 3


def define_env(env: MacrosPlugin) -> None:
    """Hook for defining variables, macros and filters.

    Args:
        env: The MkDocs macros plugin environment containing configuration
            and decorator functions for registering macros.

    """

    @env.macro
    def get_authors_data(author_uuids: str | list[str]) -> list[dict[str, Any]]:
        """Get author data for a list of UUIDs.

        Reads profiles from docs/profiles/*.md and extracts frontmatter
        metadata for each author.

        Args:
            author_uuids: A single UUID string or list of UUID strings
                identifying authors.

        Returns:
            A list of dictionaries containing author metadata from their
            profile frontmatter.

        """
        if not author_uuids:
            return []

        # env.conf['docs_dir'] is absolute path to docs directory
        docs_dir = Path(env.conf["docs_dir"])
        profiles_dir = docs_dir / "profiles"

        authors_data = []

        # Ensure author_uuids is a list
        if isinstance(author_uuids, str):
            author_uuids = [author_uuids]

        for uuid in author_uuids:
            # Handle potential file extensions or paths in UUID (though unlikely)
            clean_uuid = Path(uuid).stem
            profile_path = profiles_dir / f"{clean_uuid}.md"

            if profile_path.exists():
                try:
                    content = profile_path.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        # Extract frontmatter
                        parts = content.split("---", 2)
                        if len(parts) >= FRONTMATTER_PARTS:
                            frontmatter = yaml.safe_load(parts[1])
                            # Add UUID to data if not present
                            if "uuid" not in frontmatter:
                                frontmatter["uuid"] = clean_uuid
                            authors_data.append(frontmatter)
                except Exception as e:
                    logger.warning("Failed to load profile for UUID %s: %s", clean_uuid, e)

        return authors_data
