"""Text processing utilities."""

from __future__ import annotations

import math


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
    """Sanitize user input for LLM prompts to prevent prompt injection.

    Note: This is basic hygiene (length limit + control char removal) for user input
    used in prompts. It is NOT a full prompt-injection defense mechanism.
    """
    text = text[:max_length]
    cleaned = "".join(char for char in text if char.isprintable() or char in "\n\t")
    return "\n".join(line for line in cleaned.split("\n") if line.strip())


def calculate_reading_time(text: str) -> int:
    """Calculate the estimated reading time for a given text.

    Args:
        text: The text to calculate the reading time for.

    Returns:
        The estimated reading time in minutes, rounded up.

    """
    if not text or not text.strip():
        return 0

    words = text.split()
    word_count = len(words)

    # Average reading speed is ~200 words per minute.
    reading_time_minutes = word_count / 200

    # Round up to the nearest whole number, as is the standard convention.
    return int(math.ceil(reading_time_minutes))
