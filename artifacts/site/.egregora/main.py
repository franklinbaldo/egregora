"""MkDocs macros for Egregora site artifacts."""

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_MIN_PARTS = 3
LOGGER = logging.getLogger(__name__)


def define_env(env: Any) -> None:
    """Define variables, macros, and filters.

    - variables: the dictionary that contains the environment variables
    - macro: a decorator function, to define a macro.
    """

    @env.macro
    def get_authors_data(author_uuids: Iterable[str] | str) -> list[dict[str, Any]]:
        """Get author data for a list of UUIDs.

        Reads profiles from docs/profiles/*.md.
        """
        if not author_uuids:
            return []

        # env.conf['docs_dir'] is absolute path to docs directory
        docs_dir = Path(env.conf["docs_dir"])
        profiles_dir = docs_dir / "profiles"

        authors_data = []

        if isinstance(author_uuids, str):
            author_list = [author_uuids]
        else:
            author_list = list(author_uuids)

        for uuid in author_list:
            # Handle potential file extensions or paths in UUID (though unlikely)
            clean_uuid = Path(uuid).stem
            profile_path = profiles_dir / f"{clean_uuid}.md"

            if profile_path.exists():
                try:
                    content = profile_path.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        # Extract frontmatter
                        parts = content.split("---", 2)
                        if len(parts) >= FRONTMATTER_MIN_PARTS:
                            frontmatter = yaml.safe_load(parts[1])
                            # Add UUID to data if not present
                            if "uuid" not in frontmatter:
                                frontmatter["uuid"] = clean_uuid
                            authors_data.append(frontmatter)
                except (OSError, UnicodeError, yaml.YAMLError) as exc:
                    LOGGER.warning("Failed to parse profile %s: %s", profile_path, exc)

        return authors_data
