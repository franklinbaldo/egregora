"""Combined model and key cycling for maximum rate limit resilience.

For each model, tries all API keys before moving to next model.
Raises AllModelsExhaustedError after exhausting all Gemini models+keys.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from egregora.llm.exceptions import AllModelsExhaustedError
from egregora.llm.providers.model_cycler import (
    DEFAULT_GEMINI_MODELS,
    GeminiKeyRotator,
    default_rate_limit_check,
)

if TYPE_CHECKING:
    from collections.abc import Callable

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
        Until all models+keys exhausted
    """

    def __init__(
        self,
        models: list[str] | None = None,
        api_keys: list[str] | None = None,
        key_rotator: GeminiKeyRotator | None = None,
    ) -> None:
        """Initialize combined rotator.

        Args:
            models: List of models. Defaults to DEFAULT_GEMINI_MODELS.
            api_keys: List of API keys. If None, loads from environment.
            key_rotator: Existing key rotator instance.

        """
        self.models = models or DEFAULT_GEMINI_MODELS.copy()
        if key_rotator:
            self.key_rotator = key_rotator
        else:
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
        """Move to next model.

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
                # Do NOT reset keys here - keep cycling through keys for the new model
                # But we SHOULD clear exhausted state of keys so we can try them on new model?
                self.key_rotator.clear_exhausted()
                logger.info("[ModelKeyRotator] Rotating to model: %s", self.current_model)
                return self.current_model

        return None

    def reset_models(self) -> None:
        """Reset model iteration to start from beginning."""
        self.current_model_idx = 0
        self._exhausted_models.clear()

    def reset(self) -> None:
        """Reset everything (models and keys)."""
        self.reset_models()
        self.key_rotator.reset()

    def call_with_rotation(
        self,
        call_fn: Callable[[str, str], Any],
        is_rate_limit_error: Callable[[Exception], bool] | None = None,
    ) -> Any:
        # TODO: [Taskmaster] Refactor for clarity and simplified logic
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
            is_rate_limit_error = default_rate_limit_check

        # Only reset models for a new call, keep key rotation state (Round-Robin)
        # But we MUST clear any exhausted keys from previous calls if we want to retry them?
        # If a key failed with rate limit in prev call, should we try it again now?
        # Yes, usually rate limits are short-lived or per-request-burst.
        # So we assume fresh start for key viability, but we want to continue sequence.

        self.reset_models()
        self.key_rotator.clear_exhausted()

        last_exception: Exception | None = None

        # Try all Gemini models + keys
        while True:
            model = self.current_model
            api_key = self.key_rotator.current_key

            try:
                result = call_fn(model, api_key)

                # Success!
                # Proactively rotate key for load balancing (handled by key_rotator.rotate() via next_key behavior in simple impl?)
                # Wait, my fix to GeminiKeyRotator separated rotate() and next_key()!
                # I need to call rotate() here!

                self.key_rotator.rotate()

                return result
            except Exception as exc:
                last_exception = exc
                if is_rate_limit_error(exc):
                    # Try next key for same model (marks current as exhausted)
                    next_key = self.key_rotator.next_key()
                    if next_key:
                        # Still have keys for this model
                        continue

                    # All keys exhausted for this model, try next model
                    next_model = self._next_model()
                    if next_model:
                        # Moved to new model, exhausted keys are cleared in _next_model
                        continue

                    # All Gemini models+keys exhausted
                    logger.warning("[ModelKeyRotator] All Gemini models and keys exhausted")
                    break

                # Non-rate-limit error - propagate immediately
                # But we should probably rotate key for next time?
                self.key_rotator.rotate()
                raise

        # All models+keys exhausted
        if last_exception:
            msg = "All models and keys exhausted"
            raise AllModelsExhaustedError(
                msg,
                causes=[last_exception],
            ) from last_exception
        msg = "All models and keys exhausted"
        raise AllModelsExhaustedError(msg)
