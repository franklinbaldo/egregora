"""Combined model and key cycling for maximum rate limit resilience.

For each model, tries all API keys before moving to next model.
Only falls back to alternative providers after exhausting all Gemini models+keys.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from egregora.models.model_cycler import (
    DEFAULT_GEMINI_MODELS,
    GeminiKeyRotator,
    _default_rate_limit_check,
)

logger = logging.getLogger(__name__)


class ModelKeyRotator:
    """Rotates through all keys for each model before trying next model.

    Usage:
        rotator = ModelKeyRotator()
        result = rotator.call_with_rotation(
            lambda model, key: make_api_call(model, key),
        )

    Rotation order:
        Model1+Key1 → Model1+Key2 → Model1+Key3 →
        Model2+Key1 → Model2+Key2 → Model2+Key3 →
        ...
        THEN fallback to other providers
    """

    def __init__(
        self,
        models: list[str] | None = None,
        api_keys: list[str] | None = None,
    ) -> None:
        """Initialize combined rotator.

        Args:
            models: List of models. Defaults to DEFAULT_GEMINI_MODELS.
            api_keys: List of API keys. If None, loads from environment.

        """
        self.models = models or DEFAULT_GEMINI_MODELS.copy()
        self.key_rotator = GeminiKeyRotator(api_keys=api_keys)
        self.current_model_idx = 0
        self._exhausted_models: set[str] = set()

        logger.info(
            "[ModelKeyRotator] Initialized with %d models and %d keys",
            len(self.models),
            len(self.key_rotator.api_keys),
        )

    @property
    def current_model(self) -> str:
        """Get current model."""
        return self.models[self.current_model_idx]

    def _next_model(self) -> str | None:
        """Move to next model and reset key rotator.

        Returns:
            Next model name, or None if all exhausted.

        """
        self._exhausted_models.add(self.current_model)
        available = [m for m in self.models if m not in self._exhausted_models]

        if not available:
            logger.warning("[ModelKeyRotator] All models exhausted")
            return None

        # Find next available model
        for i in range(len(self.models)):
            next_idx = (self.current_model_idx + 1 + i) % len(self.models)
            if self.models[next_idx] not in self._exhausted_models:
                self.current_model_idx = next_idx
                self.key_rotator.reset()  # Reset keys for new model
                logger.info("[ModelKeyRotator] Rotating to model: %s", self.current_model)
                return self.current_model

        return None

    def reset(self) -> None:
        """Reset to start from beginning."""
        self.current_model_idx = 0
        self._exhausted_models.clear()
        self.key_rotator.reset()

    def call_with_rotation(
        self,
        call_fn: Callable[[str, str], Any],
        is_rate_limit_error: Callable[[Exception], bool] | None = None,
    ) -> Any:
        """Call function trying all keys for each model before rotating models.

        Args:
            call_fn: Function taking (model, api_key) and making API call.
            is_rate_limit_error: Function to check if exception is rate limit.

        Returns:
            Result from successful call.

        Raises:
            Exception: Last exception if all models+keys exhausted.

        """
        if is_rate_limit_error is None:
            is_rate_limit_error = _default_rate_limit_check

        self.reset()

        while True:
            model = self.current_model
            api_key = self.key_rotator.current_key

            try:
                result = call_fn(model, api_key)
                self.reset()
                return result
            except Exception as exc:

                if is_rate_limit_error(exc):
                    # Try next key for same model
                    next_key = self.key_rotator.next_key()
                    if next_key:
                        # Still have keys for this model
                        continue

                    # All keys exhausted for this model, try next model
                    next_model = self._next_model()
                    if next_model:
                        # Moved to new model, keys are reset
                        continue

                    # All models+keys exhausted
                    logger.exception("[ModelKeyRotator] All models and keys exhausted")
                    raise

                # Non-rate-limit error - propagate immediately
                raise

        return None  # Unreachable


def create_model_key_rotator(
    models: list[str] | None = None,
    api_keys: list[str] | None = None,
) -> ModelKeyRotator:
    """Create a combined model+key rotator.

    Args:
        models: Models from config, or None to use defaults.
        api_keys: API keys, or None to load from environment.

    Returns:
        Configured ModelKeyRotator instance.

    """
    return ModelKeyRotator(models=models, api_keys=api_keys)
