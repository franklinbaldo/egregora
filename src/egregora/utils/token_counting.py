"""Token counting utilities using tiktoken."""

from __future__ import annotations

import logging
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)

# Default encoding for Gemini (approximated using cl100k_base which is for GPT-4,
# but reasonably close for estimation if Gemini-specific not available)
DEFAULT_ENCODING = "cl100k_base"

_encoding: tiktoken.Encoding | None = None


def get_encoding() -> tiktoken.Encoding:
    """Get the global tiktoken encoding instance."""
    global _encoding  # noqa: PLW0603
    if _encoding is None:
        try:
            _encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Could not load tiktoken encoding %s, falling back to p50k_base", DEFAULT_ENCODING
            )
            _encoding = tiktoken.get_encoding("p50k_base")
    return _encoding


def count_tokens(text: str | bytes) -> int:
    """Count tokens in text string."""
    if not text:
        return 0
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback for binary data if passed by mistake, though usually shouldn't happen
            return len(text) // 4

    try:
        encoding = get_encoding()
        return len(encoding.encode(text))
    except Exception:  # noqa: BLE001
        # Fallback to heuristic if tokenizer fails
        return len(text) // 4


def estimate_tokens(obj: Any) -> int:
    """Estimate tokens for any object by converting to string first."""
    return count_tokens(str(obj))
