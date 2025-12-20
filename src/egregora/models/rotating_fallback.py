"""Rotating fallback model that cycles through keys/models on 429 errors.

This module provides a custom FallbackModel replacement that:
1. Maintains state about which model/key combination to try
2. On 429 errors, immediately rotates to the next combination
3. Only raises after all combinations are exhausted
"""

from __future__ import annotations

import logging
import threading
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

    def __init__(self, models: list[Model]) -> None:
        """Initialize with a list of model instances to rotate through.

        Args:
            models: List of Model instances. Should include variations for
                   different API keys (e.g., gemini-2.5-flash with key1,
                   gemini-2.5-flash with key2, gemini-2.0-flash with key1, etc.)
        """
        if not models:
            msg = "At least one model required"
            raise ValueError(msg)

        self._models = models
        self._current_index = 0
        self._lock = threading.Lock()
        self._consecutive_429s: dict[int, int] = {}  # Track 429s per model index

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

            # Calculate next index
            next_index = (self._current_index + 1) % len(self._models)

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

    def _all_exhausted(self) -> bool:
        """Check if all models have recent 429s (full rotation without success)."""
        with self._lock:
            # If we've hit 429 on every model at least once since last success
            return all(
                self._consecutive_429s.get(i, 0) > 0
                for i in range(len(self._models))
            )

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a request, rotating on 429 errors."""
        import httpx

        attempts = 0
        max_attempts = len(self._models) * 2  # Allow up to 2 full rotations
        last_exception: Exception | None = None

        while attempts < max_attempts:
            current_idx = self._current_index
            current_model = self._models[current_idx]

            try:
                response = await current_model.request(
                    messages, model_settings, model_request_parameters
                )
                # Success - reset 429 tracking for this model
                self._reset_429_count(current_idx)
                return response

            except ModelHTTPError as e:
                last_exception = e
                # Check if it's a 429
                if e.status_code == 429:  # noqa: PLR2004
                    attempts += 1
                    self._rotate_on_429(current_idx)

                    # If all models exhausted, break to raise
                    if self._all_exhausted():
                        logger.error(
                            "All %d models exhausted after 429s",
                            len(self._models),
                        )
                        break

                    # Continue to try next model
                    continue

                # Non-429 HTTP error - re-raise
                raise

            except httpx.HTTPStatusError as e:
                last_exception = e
                # Handle httpx-level 429 errors (in case pydantic-ai doesn't wrap them)
                if e.response.status_code == 429:  # noqa: PLR2004
                    attempts += 1
                    self._rotate_on_429(current_idx)

                    if self._all_exhausted():
                        logger.error("All models exhausted (httpx 429)")
                        break
                    continue
                raise

            except Exception as e:
                # Any other exception - check if it looks like a 429
                err_str = str(e).lower()
                if "429" in err_str or "too many requests" in err_str or "rate limit" in err_str:
                    last_exception = e
                    attempts += 1
                    self._rotate_on_429(current_idx)

                    if self._all_exhausted():
                        logger.error("All models exhausted (generic 429)")
                        break
                    continue

                # Not a 429 - re-raise immediately
                raise

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

            except ModelHTTPError as e:
                if e.status_code == 429:  # noqa: PLR2004
                    attempts += 1
                    self._rotate_on_429(current_idx)

                    if self._all_exhausted():
                        raise
                    continue
                raise

        msg = f"Max attempts ({max_attempts}) exceeded"
        raise RuntimeError(msg)
