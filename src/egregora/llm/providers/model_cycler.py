"""Gemini model and API key cycling for rate limit management.

Rotates through Gemini models and API keys on 429 errors to avoid rate limiting.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from egregora.llm.api_keys import get_google_api_keys
from egregora.llm.exceptions import AllApiKeysExhaustedError, AllModelsExhaustedError

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


# Default rotation order: cheaper/faster models first
DEFAULT_GEMINI_MODELS = [
    "gemini-2.5-flash",  # Primary model
    "gemini-2.5-flash-lite",  # Lite fallback
    "gemini-3-flash-preview",  # Preview access
]


class GeminiKeyRotator:
    """Cycle through Gemini API keys on 429 errors.

    Usage:
        rotator = GeminiKeyRotator()
        result = rotator.call_with_rotation(
            lambda key: client_with_key(key).generate(...),
        )
    """

    def __init__(self, api_keys: list[str] | None = None) -> None:
        """Initialize the key rotator.

        Args:
            api_keys: List of API keys. If None, loads from environment.

        """
        self.api_keys = api_keys or get_google_api_keys()
        if not self.api_keys:
            msg = "No API keys found. Set GEMINI_API_KEYS or GEMINI_API_KEY."
            raise ValueError(msg)
        self.current_idx = 0
        self._exhausted_keys: set[str] = set()
        logger.info("[KeyRotator] Initialized with %d API keys", len(self.api_keys))

    @property
    def current_key(self) -> str:
        """Get the current API key."""
        return self.api_keys[self.current_idx]

    @property
    def key_index(self) -> int:
        """Get the index of the current API key."""
        return self.current_idx

    def next_key(self) -> str | None:
        """Advance to the next API key.

        Returns:
            The next API key, or None if all keys are exhausted.

        """
        self._exhausted_keys.add(self.current_key)
        available = [k for k in self.api_keys if k not in self._exhausted_keys]

        if not available:
            logger.warning("[KeyRotator] All API keys exhausted")
            return None

        # Find next available key
        for i in range(len(self.api_keys)):
            next_idx = (self.current_idx + 1 + i) % len(self.api_keys)
            if self.api_keys[next_idx] not in self._exhausted_keys:
                self.current_idx = next_idx
                # Mask key for logging
                masked = self.current_key[:8] + "..." + self.current_key[-4:]
                logger.info("[KeyRotator] Rotating to key: %s", masked)
                return self.current_key

        return None

    def reset(self) -> None:
        """Reset the rotator to start fresh."""
        self.current_idx = 0
        self._exhausted_keys.clear()

    def call_with_rotation(
        self,
        call_fn: Callable[[str], Any],
        is_rate_limit_error: Callable[[Exception], bool] | None = None,
    ) -> Any:
        """Call a function with automatic key rotation.

        Features:
        1. Proactive Rotation: Rotates key after every attempt (success or fail) to distribute load.
        2. Reactive Rotation: Retries on 429 errors until all keys are exhausted.

        Args:
            call_fn: Function that takes an API key and makes the API call.
            is_rate_limit_error: Function to check if an exception is a rate limit error.

        Returns:
            The result from call_fn on success.

        Raises:
            Exception: The last exception if all keys fail.

        """
        if is_rate_limit_error is None:
            is_rate_limit_error = default_rate_limit_check

        # Track keys tried for this specific call to prevent infinite loops on 429s,
        # but don't reset the global rotator state (to maintain round-robin across different calls).
        keys_tried_for_request: set[str] = set()

        # Determine max attempts (try all keys once)
        max_attempts = len(self.api_keys)
        last_exception: Exception | None = None

        for _ in range(max_attempts):
            api_key = self.current_key

            # Avoid retrying the same key multiple times for the same request
            if api_key in keys_tried_for_request:
                # Should not happen in pure round-robin unless we wrapped around
                if len(keys_tried_for_request) >= len(self.api_keys):
                    break
                self.next_key()
                continue

            keys_tried_for_request.add(api_key)

            try:
                result = call_fn(api_key)

                # Proactive rotation: Move to next key for the *next* request
                # This ensures we distribute load even on success.
                self.next_key()

                return result
            except Exception as exc:
                last_exception = exc
                # Always rotate on error too
                self.next_key()

                if is_rate_limit_error(exc):
                    # Log warning but continue loop to try next key
                    logger.warning(
                        "[KeyRotator] Rate limit on key index %d (tried %d/%d): %s",
                        self.key_index,
                        len(keys_tried_for_request),
                        len(self.api_keys),
                        str(exc)[:100],
                    )
                    continue

                # Non-rate-limit error - propagate immediately
                raise

        # If we exit loop, we exhausted all keys with rate limits
        logger.error("[KeyRotator] All %d API keys exhausted/rate-limited", len(self.api_keys))
        # Re-raise the last exception if we have one, or a generic error
        msg = "All API keys exhausted"
        if last_exception:
            raise AllApiKeysExhaustedError(msg) from last_exception
        raise AllApiKeysExhaustedError(msg)


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
        # TODO: [Taskmaster] Refactor duplicated rotation logic
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
        # TODO: [Taskmaster] Unify state management with GeminiKeyRotator
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
            is_rate_limit_error = default_rate_limit_check

        self.reset()
        caught_exceptions: list[Exception] = []

        while True:
            model = self.current_model

            try:
                result = call_fn(model)
                # Success - reset for next call
                self.reset()
                return result
            except Exception as exc:
                if is_rate_limit_error(exc):
                    caught_exceptions.append(exc)
                    logger.warning("[ModelCycler] Rate limit on %s: %s", model, str(exc)[:100])

                    next_model = self.next_model()
                    if next_model is None:
                        logger.error("[ModelCycler] All models rate-limited")
                        msg = "All models rate-limited"
                        raise AllModelsExhaustedError(
                            msg,
                            causes=caught_exceptions,
                        ) from exc
                    continue
                # Non-rate-limit error - propagate
                raise


def default_rate_limit_check(exc: Exception) -> bool:
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


def create_key_rotator(
    api_keys: list[str] | None = None,
) -> GeminiKeyRotator:
    """Create a key rotator from config or environment.

    Args:
        api_keys: API keys, or None to load from environment.

    Returns:
        Configured GeminiKeyRotator instance.

    """
    return GeminiKeyRotator(api_keys=api_keys)
