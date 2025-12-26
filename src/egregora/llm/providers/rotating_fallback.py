"""Rotating fallback model that cycles through keys/models on 429 errors.

This module provides a custom FallbackModel replacement that:
1. Maintains state about which model/key combination to try
2. On 429 errors, immediately rotates to the next combination
3. Only raises after all combinations are exhausted
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.messages import ModelMessage, ModelResponse

logger = logging.getLogger(__name__)


class RotatingFallbackModel(Model):
    """Model wrapper that rotates through fallbacks on 429 errors.

    Unlike pydantic-ai's FallbackModel which only falls back between agent runs,
    this model rotates immediately on 429 errors within a single request.
    """

    def __init__(self, models: list[Model], model_keys: list[str | None] | None = None) -> None:
        """Initialize with a list of model instances to rotate through.

        Args:
            models: List of Model instances. Should include variations for
                   different API keys.
            model_keys: Optional tracking of which API key corresponds to each model index.
                       Used for smart exclusion (if Key A fails on Model 1, skip Model 2 if it uses Key A).

        """
        if not models:
            msg = "At least one model required"
            raise ValueError(msg)

        if model_keys and len(model_keys) != len(models):
            msg = f"model_keys length ({len(model_keys)}) must match models length ({len(models)})"
            raise ValueError(msg)

        self._models = models
        self._model_keys = model_keys
        self._current_index = 0
        self._lock = threading.Lock()
        self._consecutive_429s: dict[int, int] = {}  # Track 429s per model index
        self._excluded_keys: set[str] = set()
        self._key_cooldowns: dict[str, float] = {}  # Map of API key to expiration timestamp

    @property
    def model_name(self) -> str:
        """Return the name of the currently active model."""
        return self._models[self._current_index].model_name

    @property
    def system(self) -> str | None:
        """Return system prompt from current model."""
        return self._models[self._current_index].system

    def _rotate_on_429(self, failed_index: int) -> int:
        """Rotate to next model after 429 error.

        Args:
            failed_index: The index of the model that received 429

        Returns:
            The new current index after rotation

        """
        with self._lock:
            # Track this 429
            self._consecutive_429s[failed_index] = self._consecutive_429s.get(failed_index, 0) + 1

            # Smart Exclusion: Mark key as bad if we know it
            if self._model_keys:
                failed_key = self._model_keys[failed_index]
                if failed_key:
                    self._excluded_keys.add(failed_key)
                    logger.warning("[SmartRotation] Key ...%s excluded due to 429", failed_key[-6:])

            start_index = (self._current_index + 1) % len(self._models)
            current_time = time.time()

            # Pass 1: Look for non-excluded key that is NOT in cooldown
            candidate_index = start_index
            found_safe = False
            for _ in range(len(self._models)):
                key = self._model_keys[candidate_index] if self._model_keys else None
                # Check status
                is_excluded = key in self._excluded_keys if key else False
                cooldown_expiry = self._key_cooldowns.get(key, 0) if key else 0
                is_cooling = current_time < cooldown_expiry

                if not is_excluded and not is_cooling:
                    found_safe = True
                    break
                candidate_index = (candidate_index + 1) % len(self._models)

            # Pass 2: If no "safe" found, try any that is NOT in cooldown (even if excluded)
            if not found_safe:
                candidate_index = start_index
                for _ in range(len(self._models)):
                    key = self._model_keys[candidate_index] if self._model_keys else None
                    cooldown_expiry = self._key_cooldowns.get(key, 0) if key else 0
                    if current_time >= cooldown_expiry:
                        found_safe = True
                        break
                    candidate_index = (candidate_index + 1) % len(self._models)

            next_index = candidate_index if found_safe else start_index

            if not found_safe:
                logger.warning(
                    "[SmartRotation] ALL keys in cooldown. Forcing rotation to next model (idx %d)",
                    next_index,
                )
                # Optional: Clear exclusion list to reset cycle?
                # self._excluded_keys.clear()
                # No, keeping them excluded allows "skipping" effectively if we have mix of good/bad in future,
                # but here we just fallback to standard rotation.

            logger.info(
                "429 on %s (idx %d), rotating to %s (idx %d)",
                self._models[failed_index].model_name,
                failed_index,
                self._models[next_index].model_name,
                next_index,
            )

            self._current_index = next_index
            return next_index

    def _reset_429_count(self, index: int) -> None:
        """Reset 429 count for a model after successful request."""
        with self._lock:
            self._consecutive_429s[index] = 0
            # Also clear exclusion for this key if it succeeded!
            if self._model_keys:
                succeeded_key = self._model_keys[index]
                if succeeded_key and succeeded_key in self._excluded_keys:
                    self._excluded_keys.remove(succeeded_key)
                if succeeded_key and succeeded_key in self._key_cooldowns:
                    del self._key_cooldowns[succeeded_key]
                if succeeded_key:
                    logger.info(
                        "[SmartRotation] Key ...%s recovered/succeeded, removed from exclusion/cooldown",
                        succeeded_key[-6:],
                    )

    def _apply_rate_limit_cooldown(self, failed_index: int, error: Exception) -> None:
        """Apply cooldown to a key if rate limit information is available."""
        if not self._model_keys:
            return

        key = self._model_keys[failed_index]
        if not key:
            return

        delay = self._parse_retry_delay(error)
        if delay:
            # Add a small buffer to the requested delay
            expiry = time.time() + delay + 1.0
            with self._lock:
                self._key_cooldowns[key] = expiry
                logger.warning(
                    "[SmartRotation] Key ...%s on cooldown for %.1fs (retryDelay matched)",
                    key[-6:],
                    delay,
                )
        else:
            # Default fallback cooldown if no delay specified in error
            expiry = time.time() + 30.0
            with self._lock:
                self._key_cooldowns[key] = expiry
                logger.info("[SmartRotation] Key ...%s on default 30s cooldown", key[-6:])

    def _parse_retry_delay(self, error: Exception) -> float | None:
        """Parse retry delay from various error formats (Gemini, OpenRouter)."""
        # 1. Check ModelHTTPError (Pydantic-AI)
        if isinstance(error, ModelHTTPError) and error.body:
            try:
                # Gemini format: error.details[].retryDelay
                details = error.body.get("error", {}).get("details", [])
                for detail in details:
                    if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                        delay_str = detail.get("retryDelay", "")
                        if delay_str.endswith("s"):
                            return float(delay_str[:-1])
            except (AttributeError, ValueError):
                pass

        # 2. Check string representation for "retry after X seconds" patterns
        import re

        err_msg = str(error)
        match = re.search(r"retry after ([\d\.]+)s", err_msg, re.IGNORECASE)
        if match:
            return float(match.group(1))

        match = re.search(r"retry in ([\d\.]+)s", err_msg, re.IGNORECASE)
        if match:
            return float(match.group(1))

        return None

    def _all_exhausted(self) -> bool:
        """Check if all models have recent 429s (full rotation without success)."""
        with self._lock:
            # If we've hit 429 on every model at least once since last success
            return all(self._consecutive_429s.get(i, 0) > 0 for i in range(len(self._models)))

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a request, rotating on 429 errors."""
        attempts = 0
        max_attempts = len(self._models) * 2  # Allow up to 2 full rotations
        last_exception: Exception | None = None

        while attempts < max_attempts:
            current_idx = self._current_index
            current_model = self._models[current_idx]

            try:
                response = await current_model.request(messages, model_settings, model_request_parameters)
                # Success - reset 429 tracking for this model
                self._reset_429_count(current_idx)
                return response

            except Exception as e:
                # Always rotate on 429 or any error if we have more attempts/models
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "too many requests" in err_str or "rate limit" in err_str

                if is_rate_limit:
                    self._apply_rate_limit_cooldown(current_idx, e)

                attempts += 1
                self._rotate_on_429(current_idx)

                if self._all_exhausted() or attempts >= max_attempts:
                    logger.exception("All models exhausted or max attempts reached. Last error: %s", e)
                    raise

                logger.warning("Model index %d failed with %s, rotating...", current_idx, type(e).__name__)
                continue

        # All attempts exhausted
        if last_exception:
            raise last_exception
        msg = f"Max attempts ({max_attempts}) exceeded"
        raise RuntimeError(msg)

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> AsyncIterator[ModelResponse]:
        """Stream request with 429 rotation."""
        attempts = 0
        max_attempts = len(self._models) * 2

        while attempts < max_attempts:
            current_idx = self._current_index
            current_model = self._models[current_idx]

            try:
                async with current_model.request_stream(
                    messages, model_settings, model_request_parameters
                ) as stream:
                    self._reset_429_count(current_idx)
                    yield stream
                    return

            except Exception as e:
                # Always rotate on 429 or any error if we have more attempts/models
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "too many requests" in err_str or "rate limit" in err_str

                if is_rate_limit:
                    self._apply_rate_limit_cooldown(current_idx, e)

                attempts += 1
                self._rotate_on_429(current_idx)

                if self._all_exhausted() or attempts >= max_attempts:
                    logger.exception(
                        "All models exhausted or max attempts reached in stream. Last error: %s", e
                    )
                    raise

                logger.warning(
                    "Model index %d failed in stream with %s, rotating...", current_idx, type(e).__name__
                )
                continue

        msg = f"Max attempts ({max_attempts}) exceeded"
        raise RuntimeError(msg)
