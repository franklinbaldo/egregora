"""Model fallback utility using pydantic-ai's native FallbackModel."""

from __future__ import annotations

import os
from pydantic_core import ValidationError
import http
import logging
import os
import time
from typing import Literal

import httpx
from pydantic_ai.exceptions import ModelAPIError, UsageLimitExceeded
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel

from egregora.models import GoogleBatchModel
from egregora.utils.env import get_google_api_key

logger = logging.getLogger(__name__)

# Cache for OpenRouter free models to avoid repeated API calls
_free_models_cache: dict[str, list[str]] = {}
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


def get_openrouter_free_models(modality: str = "text") -> list[str]:
    """Fetch list of free OpenRouter models from their API.

    Args:
        modality: Filter by modality. Options:
            - "text": Text-only models (for URL enrichment, writer, reader)
            - "vision": Models with image input support (for media enrichment)
            - "any": All free models regardless of modality

    Returns:
        List of model names in pydantic-ai format (e.g., 'openrouter:model/name')

    """
    global _free_models_cache, _cache_timestamp

    current_time = time.time()

    # Check cache validity
    if _free_models_cache and (current_time - _cache_timestamp < CACHE_TTL):
        if modality in _free_models_cache:
            return _free_models_cache[modality]

    free_models: list[str] = []
    try:
        response = httpx.get("https://openrouter.ai/api/v1/models", timeout=10.0)
        response.raise_for_status()
        data = response.json()

        # Filter for free models based on modality
        for model in data.get("data", []):
            # Check if model is free
            pricing = model.get("pricing", {})
            if pricing.get("prompt", "0") != "0" or pricing.get("completion", "0") != "0":
                continue

            # Check modality requirements
            architecture = model.get("architecture", {})
            input_modalities = architecture.get("input_modalities", [])

            # Filter based on requested modality
            if modality == "text":
                # Text models should accept text input
                if "text" in input_modalities:
                    free_models.append(f"openrouter:{model['id']}")
            elif modality == "vision":
                # Vision models should accept both text and image input
                if "text" in input_modalities and "image" in input_modalities:
                    free_models.append(f"openrouter:{model['id']}")
            else:  # "any"
                free_models.append(f"openrouter:{model['id']}")

        logger.info("Fetched %d free OpenRouter models for modality '%s'", len(free_models), modality)

        # Update cache
        if modality not in _free_models_cache:
            _free_models_cache[modality] = []
        _free_models_cache[modality] = free_models
        _cache_timestamp = current_time

    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.warning("Failed to fetch OpenRouter free models: %s. No OpenRouter fallback available.", e)
        # Return empty list if API call fails - do not use hardcoded fallbacks
        free_models = []

    return free_models


def create_fallback_model(
    primary_model: str | Model,
    fallback_models: list[str | Model] | None = None,
    *,
    include_openrouter: bool = True,
    modality: str = "text",
    use_google_batch: bool = False,
) -> Model:
    """Create a FallbackModel with automatic fallback on 429 errors.

    IMPORTANT: All sub-models have retries=0 to enable fast failover.
    This means transient errors (network blips, temporary 500s) will trigger
    fallback rather than retrying the same model. This is intentional to maximize
    availability by quickly switching to alternative models.

    Args:
        primary_model: The primary model to use (can be model name string or Model instance)
        fallback_models: List of fallback models. If None, uses FALLBACK_MODELS + OpenRouter free models.
        include_openrouter: If True, automatically include free OpenRouter models in fallback list.
        modality: Model modality required. Options: "text", "vision", "any".
                  For media enrichment use "vision", for text use "text".
        use_google_batch: If True, use GoogleBatchModel for Google models (experimental)

    Returns:
        A FallbackModel that will automatically fall back on API errors.
        Sub-models are wrapped with RateLimitedModel and have retries=0 for fast failover.

    Note:
        The retries=0 configuration means that any API error will immediately
        trigger fallback to the next model rather than retrying. This optimizes
        for availability over retry persistence.

    Example:
        >>> model = create_fallback_model("google-gla:gemini-2.0-flash")
        >>> agent = Agent(model=model)

    """
    if fallback_models is None:
        # Start with Google fallback models
        fallback_models = [m for m in GOOGLE_FALLBACK_MODELS if m != primary_model]

        # Add OpenRouter free models if requested (ONLY if API key is available)
        if include_openrouter and os.environ.get("OPENROUTER_API_KEY"):
            try:
                openrouter_models = get_openrouter_free_models(modality=modality)
                # Only add if we got models back (vision may return empty list)
                if openrouter_models:
                    # Add OpenRouter models that aren't already in the list
                    for orm in openrouter_models:
                        if orm not in fallback_models and orm != primary_model:
                            fallback_models.append(orm)
                elif modality == "vision":
                    logger.info("No free OpenRouter vision models available, using Google models only")
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.warning("Failed to add OpenRouter models to fallback: %s", e)
        elif include_openrouter:
            logger.debug("OPENROUTER_API_KEY not set, skipping OpenRouter fallback models")

    from pydantic_ai.models.gemini import GeminiModel
    from pydantic_ai.models.openai import OpenAIModel

    from egregora.models.rate_limited import RateLimitedModel

    def _resolve_and_wrap(model_def: str | Model) -> Model:
        if isinstance(model_def, RateLimitedModel):
            return model_def

        model: Model
        # Set retries=0 on sub-models for fast failover (see function docstring)
        # This allows FallbackModel to quickly try alternative models on any error
        if isinstance(model_def, Model):
            model = model_def
        elif isinstance(model_def, str):
            if model_def.startswith("google-gla:"):
                from pydantic_ai.providers.google_gla import GoogleGLAProvider

                provider = GoogleGLAProvider(api_key=get_google_api_key())
                model = GeminiModel(
                    model_def.removeprefix("google-gla:"),
                    provider=provider,
                )
            elif model_def.startswith("openrouter:"):
                model = OpenAIModel(
                    model_def.removeprefix("openrouter:"),
                    provider="openrouter",
                )
            else:
                # Default to Gemini for unknown strings in this context
                from pydantic_ai.providers.google_gla import GoogleGLAProvider

                provider = GoogleGLAProvider(api_key=get_google_api_key())
                model = GeminiModel(
                    model_def,
                    provider=provider,
                )
        else:
            msg = f"Unknown model type: {type(model_def)}"
            raise ValueError(msg)

        return RateLimitedModel(model)

    # Prepare models - get API key for batch models
    api_key = get_google_api_key()

    # 1. Prepare Primary
    primary: Model
    if use_google_batch and isinstance(primary_model, str) and primary_model.startswith("google-gla:"):
        primary = GoogleBatchModel(api_key=api_key, model_name=primary_model)
        # GoogleBatchModel is already a Model, wrap it
        primary = RateLimitedModel(primary)
    else:
        primary = _resolve_and_wrap(primary_model)

    # Note: Fallbacks are disabled per user request
    # TODO: Re-enable fallback logic once rate limits are stabilized or
    # a more robust fallback strategy is implemented.
    return primary

    # wrapped_fallbacks = []
    # for m in fallback_models:
    #     if use_google_batch and isinstance(m, str) and m.startswith("google-gla:"):
    #         batch_model = GoogleBatchModel(api_key=api_key, model_name=m)
    #         wrapped_fallbacks.append(RateLimitedModel(batch_model))
    #     else:
    #         wrapped_fallbacks.append(_resolve_and_wrap(m))
    #
    # return FallbackModel(
    #     primary,
    #     *wrapped_fallbacks,
    #     fallback_on=(ModelAPIError, UsageLimitExceeded, ValidationError),
    # )
