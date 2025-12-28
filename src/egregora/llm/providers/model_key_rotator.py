"""Combined model and key cycling for maximum rate limit resilience.

For each model, tries all API keys before moving to next model.
Only falls back to alternative providers after exhausting all Gemini models+keys.
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
        THEN fallback to other providers
    """

    def __init__(
        self,
        models: list[str] | None = None,
        api_keys: list[str] | None = None,
        *,
        include_openrouter: bool = True,
    ) -> None:
        """Initialize combined rotator.

        Args:
            models: List of models. Defaults to DEFAULT_GEMINI_MODELS.
            api_keys: List of API keys. If None, loads from environment.
            include_openrouter: If True, fall back to OpenRouter after Gemini exhaustion.

        """
        self.models = models or DEFAULT_GEMINI_MODELS.copy()
        self.key_rotator = GeminiKeyRotator(api_keys=api_keys)
        self.current_model_idx = 0
        self._exhausted_models: set[str] = set()
        self._include_openrouter = include_openrouter
        self._openrouter_models: list[str] = []
        self._openrouter_idx = 0
        self._in_openrouter_fallback = False

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
        import os

        if is_rate_limit_error is None:
            is_rate_limit_error = default_rate_limit_check

        self.reset()
        last_exception: Exception | None = None

        # Phase 1: Try all Gemini models + keys
        while True:
            model = self.current_model
            api_key = self.key_rotator.current_key

            try:
                result = call_fn(model, api_key)
                self.reset()
                return result
            except Exception as exc:
                last_exception = exc
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

                    # All Gemini models+keys exhausted, try OpenRouter fallback
                    logger.warning(
                        "[ModelKeyRotator] All Gemini models and keys exhausted, trying OpenRouter fallback"
                    )
                    break

                # Non-rate-limit error - propagate immediately
                raise

        # Phase 2: OpenRouter fallback
        if self._include_openrouter:
            openrouter_key = os.environ.get("OPENROUTER_API_KEY")
            if openrouter_key:
                # Lazy load OpenRouter models
                if not self._openrouter_models:
                    from egregora.utils.model_fallback import get_openrouter_free_models

                    self._openrouter_models = get_openrouter_free_models(modality="text")
                    logger.info(
                        "[ModelKeyRotator] Fetched %d OpenRouter models for fallback",
                        len(self._openrouter_models),
                    )

                # Try each OpenRouter model
                for or_model in self._openrouter_models:
                    # Strip the "openrouter:" prefix for the model name
                    model_name = or_model.removeprefix("openrouter:")
                    try:
                        logger.info("[ModelKeyRotator] Trying OpenRouter model: %s", model_name)
                        result = call_fn(model_name, openrouter_key)
                        self.reset()
                        return result
                    except Exception as exc:  # noqa: BLE001
                        last_exception = exc
                        if is_rate_limit_error(exc):
                            logger.warning(
                                "[ModelKeyRotator] OpenRouter model %s rate limited, trying next", model_name
                            )
                            continue
                        # Non-rate-limit error on OpenRouter - try next model
                        logger.warning("[ModelKeyRotator] OpenRouter model %s failed: %s", model_name, exc)
                        continue

                logger.exception("[ModelKeyRotator] All OpenRouter models also exhausted")
            else:
                logger.warning("[ModelKeyRotator] OPENROUTER_API_KEY not set, cannot use OpenRouter fallback")

        # All options exhausted
        if last_exception:
            raise AllModelsExhaustedError(
                "All models and keys exhausted",
                causes=[last_exception],
            ) from last_exception
        msg = "All models and keys exhausted"
        raise AllModelsExhaustedError(msg)


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
