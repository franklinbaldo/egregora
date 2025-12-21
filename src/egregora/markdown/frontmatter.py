"""Helpers for parsing YAML frontmatter from Markdown content."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import frontmatter
import yaml

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter using python-frontmatter.

    Args:
        content: Markdown content that may include frontmatter.

    Returns:
        Tuple of (metadata dict, body string). If parsing fails or metadata is not a
        mapping, metadata will be an empty dict and the original content is returned.

    """
    try:
        parsed = frontmatter.loads(content)
    except (yaml.YAMLError, ValueError) as exc:
        logger.warning("Failed to parse frontmatter content: %s", exc)
        return {}, content

    raw_metadata = parsed.metadata or {}
    if not isinstance(raw_metadata, dict):
        logger.warning("Frontmatter metadata is not a mapping: %s", type(raw_metadata).__name__)
        metadata: dict[str, Any] = {}
    else:
        metadata = dict(raw_metadata)

    body = parsed.content if isinstance(parsed.content, str) else str(parsed.content)
    return metadata, body


def parse_frontmatter_file(path: Path, *, encoding: str = "utf-8") -> tuple[dict[str, Any], str]:
    """Read a Markdown file and parse its frontmatter.

    Args:
        path: File system path to the Markdown document.
        encoding: File encoding used to read the file.

    Returns:
        Tuple of (metadata dict, body string).

    Raises:
        OSError: If the file cannot be read.

    """
    content = path.read_text(encoding=encoding)
    return parse_frontmatter(content)


def read_frontmatter_only(path: Path, *, encoding: str = "utf-8") -> dict[str, Any]:
    """Read only the frontmatter from a Markdown file, stopping at the delimiter.

    This avoids reading the entire file into memory when only metadata is needed.

    Args:
        path: File system path to the Markdown document.
        encoding: File encoding used to read the file.

    Returns:
        Metadata dict. Returns empty dict if no frontmatter found or parsing fails.

    """
    try:
        with path.open("r", encoding=encoding) as f:
            first_line = f.readline()
            if not first_line.startswith("---"):
                return {}

            lines = []
            for line in f:
                if line.rstrip() == "---":
                    break
                lines.append(line)
            else:
                # EOF reached without closing '---', treat as invalid frontmatter
                # or possibly the whole file is frontmatter?
                # Standard behavior dictates closing delimiter.
                # However, python-frontmatter might be more lenient.
                # We'll be strict here: no closing delimiter = no frontmatter.
                return {}

            yaml_content = "".join(lines)
            data = yaml.safe_load(yaml_content)
            if isinstance(data, dict):
                return data
            return {}

    except (OSError, yaml.YAMLError) as exc:
        logger.debug("Failed to read frontmatter from %s: %s", path, exc)
        return {}
