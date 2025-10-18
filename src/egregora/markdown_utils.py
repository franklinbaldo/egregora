"""Lightweight helpers for formatting Markdown with optional dependencies."""

from __future__ import annotations

import logging

try:  # pragma: no cover - optional dependency
    import mdformat  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    mdformat = None  # type: ignore[assignment]

FRONT_MATTER_DELIMITER = "---"

logger = logging.getLogger(__name__)


def _split_front_matter(text: str) -> tuple[str, str]:
    stripped = text.lstrip()
    prefix_len = len(text) - len(stripped)
    prefix = text[:prefix_len]

    if not stripped.startswith(f"{FRONT_MATTER_DELIMITER}\n"):
        return "", text

    end_marker = f"\n{FRONT_MATTER_DELIMITER}"
    end_index = stripped.find(end_marker, len(FRONT_MATTER_DELIMITER) + 1)
    if end_index == -1:
        return "", text

    end_index += len(end_marker)
    front_matter = stripped[:end_index]
    remainder = stripped[end_index:]
    return prefix + front_matter + "\n", remainder


def format_markdown(text: str, *, assume_front_matter: bool = False) -> str:
    """Return ``text`` formatted with mdformat when available."""

    if not text:
        return text

    if mdformat is None:
        logger.warning("mdformat is not installed. Skipping Markdown formatting.")
        return text

    if assume_front_matter:
        front_matter, body = _split_front_matter(text)
        if not front_matter:
            body = text
            front_matter = ""
        formatted_body = _format_markdown_block(body)
        if front_matter:
            return f"{front_matter}{formatted_body.lstrip()}"
        return formatted_body

    return _format_markdown_block(text)


def _format_markdown_block(block: str) -> str:
    try:
        formatted = mdformat.text(block, options={"wrap": 88})
    except Exception as e:  # pragma: no cover - defensive fallback
        logger.warning(f"Failed to format Markdown: {e}")
        return block
    return formatted


__all__ = ["format_markdown"]
