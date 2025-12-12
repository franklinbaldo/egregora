"""Gemini model cycling for rate limit management.

Rotates through Gemini models on 429 errors to avoid rate limiting.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


# Default rotation order: cheaper/faster models first
DEFAULT_GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemma-3-12b-it",
    "gemma-3-27b-it",
    "gemini-2.5-pro",
]


class GeminiModelCycler:
    """Cycle through Gemini models on 429 errors.

    Usage:
        cycler = GeminiModelCycler()
        result = cycler.call_with_rotation(
            lambda model: client.generate(model=model, ...),
            is_rate_limit_error=lambda e: "429" in str(e),
        )
    """

    def __init__(
        self,
        models: list[str] | None = None,
        max_retries_per_model: int = 1,
    ) -> None:
        """Initialize the model cycler.

        Args:
            models: List of Gemini model names to cycle through.
                   Defaults to DEFAULT_GEMINI_MODELS.
            max_retries_per_model: Max retries per model before rotating.

        """
        self.models = models or DEFAULT_GEMINI_MODELS.copy()
        self.max_retries_per_model = max_retries_per_model
        self.current_idx = 0
        self._exhausted_models: set[str] = set()

    @property
    def current_model(self) -> str:
        """Get the current model in the rotation."""
        return self.models[self.current_idx]

    def next_model(self) -> str | None:
        """Advance to the next model in rotation.

        Returns:
            The next model name, or None if all models are exhausted.

        """
        self._exhausted_models.add(self.current_model)
        available = [m for m in self.models if m not in self._exhausted_models]

        if not available:
            logger.warning("[ModelCycler] All models exhausted")
            return None

        # Find next available model
        for i in range(len(self.models)):
            next_idx = (self.current_idx + 1 + i) % len(self.models)
            if self.models[next_idx] not in self._exhausted_models:
                self.current_idx = next_idx
                logger.info("[ModelCycler] Rotating to model: %s", self.current_model)
                return self.current_model

        return None

    def reset(self) -> None:
        """Reset the cycler to start fresh."""
        self.current_idx = 0
        self._exhausted_models.clear()

    def call_with_rotation(
        self,
        call_fn: Callable[[str], Any],
        is_rate_limit_error: Callable[[Exception], bool] | None = None,
    ) -> Any:
        """Call a function with automatic model rotation on rate limit errors.

        Args:
            call_fn: Function that takes a model name and makes the API call.
            is_rate_limit_error: Function to check if an exception is a rate limit error.
                                Defaults to checking for "429" or "Too Many Requests" in message.

        Returns:
            The result from call_fn on success.

        Raises:
            Exception: The last exception if all models fail.

        """
        if is_rate_limit_error is None:
            is_rate_limit_error = self._default_rate_limit_check

        last_exception: Exception | None = None
        self.reset()

        while True:
            model = self.current_model

            try:
                result = call_fn(model)
                # Success - reset for next call
                self.reset()
                return result
            except Exception as exc:
                last_exception = exc

                if is_rate_limit_error(exc):
                    logger.warning("[ModelCycler] Rate limit on %s: %s", model, str(exc)[:100])
                    next_model = self.next_model()
                    if next_model is None:
                        logger.error("[ModelCycler] All models rate-limited")
                        raise
                    continue
                # Non-rate-limit error - propagate
                raise

        # Should not reach here, but satisfy type checker
        if last_exception:
            raise last_exception

    @staticmethod
    def _default_rate_limit_check(exc: Exception) -> bool:
        """Default check for rate limit errors."""
        msg = str(exc).lower()
        return "429" in msg or "too many requests" in msg or "rate limit" in msg


def create_model_cycler(
    config_models: list[str] | None = None,
) -> GeminiModelCycler:
    """Create a model cycler from config.

    Args:
        config_models: Models from config, or None to use defaults.

    Returns:
        Configured GeminiModelCycler instance.

    """
    return GeminiModelCycler(models=config_models)
