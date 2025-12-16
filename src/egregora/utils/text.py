"""Text processing utilities."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: ~4 chars per token).

    Useful for quick size checks without loading a tokenizer.

    Args:
        text: Input text

    Returns:
        Estimated number of tokens

    """
    if not text:
        return 0
    return len(text) // 4
