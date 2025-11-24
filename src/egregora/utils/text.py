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


def sanitize_prompt_input(text: str, max_length: int = 2000) -> str:
    """Sanitize user input for LLM prompts to prevent prompt injection."""
    text = text[:max_length]
    cleaned = "".join(char for char in text if char.isprintable() or char in "\n\t")
    return "\n".join(line for line in cleaned.split("\n") if line.strip())
