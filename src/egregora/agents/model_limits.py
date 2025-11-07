"""Model context window limits and token utilities.

This module provides utilities for:
- Getting model context window limits
- Estimating token counts
- Validating prompts fit within limits

Context window validation is critical for production use - prompts that exceed
limits cause API failures or silent truncation, wasting tokens and degrading quality.
"""

import logging

logger = logging.getLogger(__name__)

# Gemini model context limits (input tokens)
# Source: https://ai.google.dev/gemini-api/docs/models/gemini
KNOWN_MODEL_LIMITS = {
    # Gemini 2.0 family
    "gemini-2.0-flash-exp": 1_048_576,  # 1M tokens
    "gemini-2.0-flash-thinking-exp": 32_768,  # 32k tokens (experimental thinking mode)
    # Gemini 1.5 family
    "gemini-1.5-flash": 1_048_576,  # 1M tokens
    "gemini-1.5-flash-8b": 1_048_576,  # 1M tokens
    "gemini-1.5-flash-latest": 1_048_576,  # 1M tokens
    "gemini-1.5-pro": 2_097_152,  # 2M tokens
    "gemini-1.5-pro-latest": 2_097_152,  # 2M tokens
    # Gemini 1.0 family (older, smaller limits)
    "gemini-pro": 32_768,  # 32k tokens
    "gemini-1.0-pro": 32_768,  # 32k tokens
    # Embeddings
    "text-embedding-004": 2048,  # 2k tokens (for embeddings, not generation)
}


def estimate_tokens(text: str) -> int:
    """Estimate token count using character-based approximation.

    Gemini uses SentencePiece tokenization. For English text, a rough approximation
    is ~4 characters per token. This is faster than actual tokenization and
    sufficient for context window validation (we add safety margins anyway).

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count

    Examples:
        >>> estimate_tokens("Hello world")
        2  # "Hello world" is 11 chars → ~2.75 tokens → 2
        >>> estimate_tokens("A" * 400)
        100  # 400 chars → 100 tokens

    """
    return len(text) // 4


def get_model_context_limit(model_name: str) -> int:
    """Get input token limit for a model.

    Args:
        model_name: Model name (e.g., "models/gemini-2.0-flash-exp",
                    "google-gla:gemini-1.5-pro", or "gemini-1.5-flash")

    Returns:
        Input token limit for the model. Defaults to conservative 128k if unknown.

    Examples:
        >>> get_model_context_limit("models/gemini-2.0-flash-exp")
        1048576
        >>> get_model_context_limit("google-gla:gemini-1.5-pro")
        2097152
        >>> get_model_context_limit("unknown-model")
        128000

    """
    # Strip common prefixes
    clean_name = (
        model_name.replace("models/", "")
        .replace("google-gla:", "")
        .replace("google-vertex:", "")
        .replace("gemini-", "gemini-")  # Normalize gemini- prefix
    )

    # Try exact match
    limit = KNOWN_MODEL_LIMITS.get(clean_name)
    if limit:
        logger.debug("Found context limit for %s: %s tokens", model_name, limit)
        return limit

    # Try fuzzy match (e.g., "gemini-1.5-flash-001" → "gemini-1.5-flash")
    for known_model, known_limit in KNOWN_MODEL_LIMITS.items():
        if clean_name.startswith(known_model):
            logger.debug(
                "Fuzzy matched %s to %s: %s tokens",
                model_name,
                known_model,
                known_limit,
            )
            return known_limit

    # Default to conservative 128k for unknown models
    logger.warning(
        "Unknown model %s, defaulting to 128k token limit",
        model_name,
    )
    return 128_000


def validate_prompt_fits(
    prompt: str,
    model_name: str,
    *,
    safety_margin: float = 0.1,
    max_prompt_tokens: int | None = 100_000,
    use_full_context_window: bool = False,
) -> tuple[bool, int, int]:
    """Validate that a prompt fits within model's context window.

    Args:
        prompt: Full prompt to send to model
        model_name: Model name to check limits for
        safety_margin: Safety margin as fraction of limit (default 0.1 = 10%)
        max_prompt_tokens: Maximum tokens allowed (default 100k cap, even if model supports more)
        use_full_context_window: If True, ignore max_prompt_tokens and use full model limit

    Returns:
        Tuple of (fits, estimated_tokens, effective_limit)

    Examples:
        >>> fits, tokens, limit = validate_prompt_fits("Hello" * 1000, "gemini-1.5-flash")
        >>> fits
        True
        >>> tokens
        1250  # ~5000 chars / 4
        >>> limit
        90000  # min(100k default cap, 1M model limit) - 10% margin

    """
    estimated_tokens = estimate_tokens(prompt)
    context_limit = get_model_context_limit(model_name)

    # Apply max_prompt_tokens cap unless use_full_context_window is True
    if not use_full_context_window and max_prompt_tokens is not None:
        context_limit = min(context_limit, max_prompt_tokens)

    # Apply safety margin (reserve space for tool calls, continuations, etc.)
    effective_limit = int(context_limit * (1 - safety_margin))

    fits = estimated_tokens <= effective_limit

    if not fits:
        logger.warning(
            "Prompt exceeds context limit: %d tokens > %d effective limit (%d total - %d%% margin) for model %s",
            estimated_tokens,
            effective_limit,
            context_limit,
            int(safety_margin * 100),
            model_name,
        )

    return fits, estimated_tokens, effective_limit


__all__ = [
    "KNOWN_MODEL_LIMITS",
    "estimate_tokens",
    "get_model_context_limit",
    "validate_prompt_fits",
]
