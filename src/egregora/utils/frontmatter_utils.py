"""Helpers for parsing YAML frontmatter from Markdown content."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import frontmatter

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
    except Exception as exc:  # broad catch to avoid breaking indexing on malformed files
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
