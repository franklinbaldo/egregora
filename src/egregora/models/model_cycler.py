"""Gemini model and API key cycling for rate limit management.

Rotates through Gemini models and API keys on 429 errors to avoid rate limiting.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


# Default rotation order: cheaper/faster models first
DEFAULT_GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-pro",
]


def get_api_keys() -> list[str]:
    """Load API keys from environment.

    Supports multiple keys via:
    - GEMINI_API_KEYS (comma-separated)
    - GEMINI_API_KEY (single key, fallback)
    - GOOGLE_API_KEY (single key, fallback)

    Returns:
        List of API keys, or empty list if none found.

    """
    # Check for comma-separated list first
    keys_str = os.environ.get("GEMINI_API_KEYS", "")
    if keys_str:
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if keys:
            logger.debug("[KeyRotator] Loaded %d API keys from GEMINI_API_KEYS", len(keys))
            return keys

    # Fall back to single key
    single_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if single_key:
        return [single_key]

    return []


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
        self.api_keys = api_keys or get_api_keys()
        if not self.api_keys:
            msg = "No API keys found. Set GEMINI_API_KEYS or GEMINI_API_KEY."
            raise ValueError(msg)
        self.current_idx = 0
        self._exhausted_keys: set[str] = set()
        logger.info("[KeyRotator] Initialized with %d API keys (starting with key[0])", len(self.api_keys))

    @property
    def current_key(self) -> str:
        """Get the current API key."""
        return self.api_keys[self.current_idx]

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
                # Mask key for logging - include key ID for debugging
                masked = self.current_key[:8] + "..." + self.current_key[-4:]
                logger.info("[KeyRotator] Rotating to key[%d]: %s", self.current_idx, masked)
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
        """Call a function with automatic key rotation on rate limit errors.

        Args:
            call_fn: Function that takes an API key and makes the API call.
            is_rate_limit_error: Function to check if an exception is a rate limit error.

        Returns:
            The result from call_fn on success.

        Raises:
            Exception: The last exception if all keys fail.

        """
        if is_rate_limit_error is None:
            is_rate_limit_error = _default_rate_limit_check

        self.reset()

        while True:
            api_key = self.current_key
            key_idx = self.current_idx  # Log which key we're using

            try:
                logger.debug("[KeyRotator] Trying key[%d]", key_idx)
                result = call_fn(api_key)
                self.reset()
                return result
            except Exception as exc:

                if is_rate_limit_error(exc):
                    masked = api_key[:8] + "..." + api_key[-4:]
                    logger.warning("[KeyRotator] Rate limit on key[%d] %s: %s", key_idx, masked, str(exc)[:100])
                    next_key = self.next_key()  # Immediate rotation - no wait!
                    if next_key is None:
                        logger.exception("[KeyRotator] All API keys rate-limited")
                        raise
                    continue
                raise

        return None  # Unreachable, but satisfies type checker


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
            is_rate_limit_error = _default_rate_limit_check

        self.reset()

        while True:
            model = self.current_model

            try:
                result = call_fn(model)
                # Success - reset for next call
                self.reset()
                return result
            except Exception as exc:

                if is_rate_limit_error(exc):
                    logger.warning("[ModelCycler] Rate limit on %s: %s", model, str(exc)[:100])
                    next_model = self.next_model()
                    if next_model is None:
                        logger.exception("[ModelCycler] All models rate-limited")
                        raise
                    continue
                # Non-rate-limit error - propagate
                raise

        return None  # Unreachable, but satisfies type checker


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
