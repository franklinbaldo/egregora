"""Model fallback utility using pydantic-ai's native FallbackModel."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import httpx
from pydantic_ai.models.fallback import FallbackModel

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)

# Cache for OpenRouter free models to avoid repeated API calls
_free_models_cache: list[str] | None = None
_cache_timestamp: float = 0
CACHE_TTL = 3600  # Cache for 1 hour

# Priority order for Google models
GOOGLE_FALLBACK_MODELS = [
    "google-gla:gemini-2.5-pro",
    "google-gla:gemini-2.5-flash",
    "google-gla:gemini-2.0-flash",
    "google-gla:gemini-2.5-flash-lite",
]

# Priority order for text agents (Google -> OpenRouter free models)
# Will be populated dynamically with free OpenRouter models
FALLBACK_MODELS = GOOGLE_FALLBACK_MODELS.copy()


def get_openrouter_free_models() -> list[str]:
    """Fetch list of free OpenRouter models from their API.

    Returns:
        List of model names in pydantic-ai format (e.g., 'openrouter:model/name')

    """
    global _free_models_cache, _cache_timestamp  # noqa: PLW0603

    # Check cache
    if _free_models_cache and (time.time() - _cache_timestamp) < CACHE_TTL:
        return _free_models_cache

    free_models: list[str] = []
    try:
        response = httpx.get("https://openrouter.ai/api/v1/models", timeout=10.0)
        response.raise_for_status()
        data = response.json()

        # Filter for free models and convert to pydantic-ai format
        free_models = [
            f"openrouter:{model['id']}"
            for model in data.get("data", [])
            if model.get("pricing", {}).get("prompt", "0") == "0"
            and model.get("pricing", {}).get("completion", "0") == "0"
        ]

        # Update cache
        _free_models_cache = free_models
        _cache_timestamp = time.time()

        logger.info("Fetched %d free OpenRouter models", len(free_models))
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.warning("Failed to fetch OpenRouter free models: %s. Using fallback list.", e)
        # Return hardcoded fallback if API call fails
        free_models = [
            "openrouter:x-ai/grok-beta",
            "openrouter:google/gemma-2-9b-it:free",
            "openrouter:meta-llama/llama-3.1-8b-instruct:free",
            "openrouter:mistralai/mistral-7b-instruct:free",
        ]

    return free_models


def create_fallback_model(
    primary_model: str | Model,
    fallback_models: list[str | Model] | None = None,
    *,
    include_openrouter: bool = True,
) -> Model:
    """Create a FallbackModel with automatic fallback on 429 errors.

    Args:
        primary_model: The primary model to use (can be model name string or Model instance)
        fallback_models: List of fallback models. If None, uses FALLBACK_MODELS + OpenRouter free models.
        include_openrouter: If True, automatically include free OpenRouter models in fallback list.

    Returns:
        A FallbackModel that will automatically fall back on API errors.

    Example:
        >>> model = create_fallback_model("google-gla:gemini-2.0-flash")
        >>> agent = Agent(model=model)

    """
    if fallback_models is None:
        # Start with Google fallback models
        fallback_models = [m for m in GOOGLE_FALLBACK_MODELS if m != primary_model]

        # Add OpenRouter free models if requested
        if include_openrouter:
            try:
                openrouter_models = get_openrouter_free_models()
                # Add OpenRouter models that aren't already in the list
                for orm in openrouter_models:
                    if orm not in fallback_models and orm != primary_model:
                        fallback_models.append(orm)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.warning("Failed to add OpenRouter models to fallback: %s", e)

    # FallbackModel defaults to falling back on ModelAPIError (which includes 429)
    return FallbackModel(
        primary_model,
        *fallback_models,
    )
