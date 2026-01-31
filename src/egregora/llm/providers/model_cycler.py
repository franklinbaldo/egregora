"""Gemini model and API key cycling for rate limit management.

Rotates through Gemini models and API keys on 429 errors to avoid rate limiting.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from egregora.llm.api_keys import get_google_api_keys

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

    def rotate(self) -> str:
        """Proactively rotate to the next key without marking current as exhausted.

        Used for load balancing on success.
        """
        self.current_idx = (self.current_idx + 1) % len(self.api_keys)
        # Skip exhausted keys if any (though typically rotate is used when keys are good)
        for _ in range(len(self.api_keys)):
            if self.api_keys[self.current_idx] not in self._exhausted_keys:
                break
            self.current_idx = (self.current_idx + 1) % len(self.api_keys)

        return self.current_key

    def next_key(self) -> str | None:
        """Advance to the next API key and mark current as exhausted.

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

    def clear_exhausted(self) -> None:
        """Clear the set of exhausted keys, but keep the current index."""
        self._exhausted_keys.clear()

    def reset(self) -> None:
        """Reset the rotator to start fresh."""
        self.current_idx = 0
        self.clear_exhausted()

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

        for _ in range(max_attempts):
            api_key = self.current_key

            # Avoid retrying the same key multiple times for the same request
            if api_key in keys_tried_for_request:
                # Should not happen in pure round-robin unless we wrapped around
                if len(keys_tried_for_request) >= len(self.api_keys):
                    break
                self.rotate()  # Skip to next
                continue

            keys_tried_for_request.add(api_key)

            try:
                result = call_fn(api_key)

                # Proactive rotation: Move to next key for the *next* request
                # This ensures we distribute load even on success.
                self.rotate()

                return result
            except Exception as exc:
                # Always rotate on error too
                # If rate limit, we mark exhausted via next_key()
                # If other error, we just rotate() to try next key?
                # No, unrelated errors usually shouldn't retry?
                # But original code retried all errors?
                # "except Exception as exc: ... Non-rate-limit error - propagate immediately"

                if is_rate_limit_error(exc):
                    # Mark current as exhausted and move next
                    self.next_key()

                    # Log warning but continue loop to try next key
                    logger.warning(
                        "[KeyRotator] Rate limit on key index %d (tried %d/%d): %s",
                        self.key_index,
                        len(keys_tried_for_request),
                        len(self.api_keys),
                        str(exc)[:100],
                    )
                    continue

                # Non-rate-limit error
                # We should probably rotate anyway so next call uses next key?
                self.rotate()
                raise

        # If we exit loop, we exhausted all keys with rate limits
        logger.error("[KeyRotator] All %d API keys exhausted/rate-limited", len(self.api_keys))
        # Re-raise the last exception if we have one, or a generic error
        msg = "All API keys exhausted"
        raise RuntimeError(msg)


def default_rate_limit_check(exc: Exception) -> bool:
    """Default check for rate limit errors."""
    msg = str(exc).lower()
    return "429" in msg or "too many requests" in msg or "rate limit" in msg
