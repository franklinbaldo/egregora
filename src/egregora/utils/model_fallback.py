"""Model fallback utility using pydantic-ai's native FallbackModel."""

from __future__ import annotations

import logging
import os
import time

import httpx
from pydantic_ai.models import Model

from egregora.llm.providers import GoogleBatchModel
from egregora.utils.env import get_google_api_key, get_google_api_keys
from egregora.utils.exceptions import ModelConfigurationError, OpenRouterAPIError

logger = logging.getLogger(__name__)


# Cache for OpenRouter free models to avoid repeated API calls
_free_models_cache: dict[str, list[str]] = {}
_cache_timestamp: float = 0
CACHE_TTL = 3600  # Cache for 1 hour

# Priority order for Google models
GOOGLE_FALLBACK_MODELS = [
    "google-gla:gemini-2.5-flash",
    "google-gla:gemini-3-flash-preview",
    "google-gla:gemini-2.5-pro",
    "google-gla:gemini-2.0-flash",
    "google-gla:gemini-2.0-flash-exp",
]


def get_openrouter_free_models(modality: str = "text", *, require_tools: bool = False) -> list[str]:
    """Fetch list of free OpenRouter models from their API.

    Args:
        modality: Filter by modality. Options:
            - "text": Text-only models (for URL enrichment, writer, reader)
            - "vision": Models with image input support (for media enrichment)
            - "any": All free models regardless of modality
        require_tools: If True, only return models that support tool-calling.

    Returns:
        List of model names in pydantic-ai format (e.g., 'openrouter:model/name')

    """
    global _free_models_cache, _cache_timestamp  # noqa: PLW0602

    current_time = time.time()

    # Check cache validity
    cache_key = f"{modality}_tools" if require_tools else modality
    if _free_models_cache and (current_time - _cache_timestamp < CACHE_TTL):
        if cache_key in _free_models_cache:
            return _free_models_cache[cache_key]

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
            supports_tools = (
                architecture.get("tool_use", False) or "tools" in str(model.get("description", "")).lower()
            )

            # Filter based on tool support if required
            if require_tools and not supports_tools:
                continue

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

        logger.info(
            "Fetched %d free OpenRouter models (modality=%s, require_tools=%s)",
            len(free_models),
            modality,
            require_tools,
        )

        # Update cache
        _free_models_cache[cache_key] = free_models
        _cache_timestamp = current_time

    except (httpx.HTTPError, httpx.TimeoutException) as e:
        msg = f"Failed to fetch OpenRouter free models: {e}"
        raise OpenRouterAPIError(msg) from e

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
        >>> model = create_fallback_model("google-gla:gemini-2.0-flash-exp")
        >>> agent = Agent(model=model)

    """
    openrouter_models: list[str] = []
    if include_openrouter and os.environ.get("OPENROUTER_API_KEY"):
        try:
            # Most of our text models use tools (writer, agents)
            require_tools = modality == "text"
            openrouter_models = get_openrouter_free_models(modality=modality, require_tools=require_tools)
            if not openrouter_models and modality == "vision":
                logger.info("No free OpenRouter vision models available, using Google models only")
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning("Failed to add OpenRouter models to fallback: %s", e)
    elif include_openrouter:
        logger.debug("OPENROUTER_API_KEY not set, skipping OpenRouter fallback models")

    if fallback_models is None:
        # Start with Google fallback models.
        fallback_models = [m for m in GOOGLE_FALLBACK_MODELS if m != primary_model]

        # Prefer OpenRouter models ahead of Google fallbacks when Google is primary.
        if openrouter_models and isinstance(primary_model, str) and primary_model.startswith("google-gla:"):
            fallback_models = [
                *[orm for orm in openrouter_models if orm != primary_model],
                *fallback_models,
            ]
        else:
            # Append OpenRouter models at the end when primary isn't Google.
            for orm in openrouter_models:
                if orm not in fallback_models and orm != primary_model:
                    fallback_models.append(orm)

    def _resolve_and_wrap(model_def: str | Model, api_key: str | None = None) -> Model:
        # Imports moved here to avoid top-level circular dependencies,
        # but ruff complains. We suppress the warning as this is intentional
        # for lazy loading heavy model dependencies only when needed.
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        from egregora.llm.providers.rate_limited import RateLimitedModel

        if isinstance(model_def, RateLimitedModel):
            return model_def

        model: Model
        # Set retries=0 on sub-models for fast failover (see function docstring)
        # This allows FallbackModel to quickly try alternative models on any error
        if isinstance(model_def, Model):
            model = model_def
        elif isinstance(model_def, str):
            if model_def.startswith("google-gla:"):
                provider = GoogleProvider(api_key=api_key or get_google_api_key())
                model = GoogleModel(
                    model_def.removeprefix("google-gla:"),
                    provider=provider,
                )
            elif model_def.startswith("openrouter:"):
                # Use pydantic-ai's dedicated OpenRouter support
                # See: https://ai.pydantic.dev/models/openrouter/
                from pydantic_ai.models.openrouter import OpenRouterModel
                from pydantic_ai.providers.openrouter import OpenRouterProvider

                openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
                if not openrouter_api_key:
                    msg = "OPENROUTER_API_KEY environment variable required for OpenRouter models"
                    raise ModelConfigurationError(msg)

                openrouter_provider = OpenRouterProvider(api_key=openrouter_api_key)
                model = OpenRouterModel(
                    model_def.removeprefix("openrouter:"),
                    provider=openrouter_provider,
                )
            else:
                # Default to Google for unknown strings in this context
                provider = GoogleProvider(api_key=api_key or get_google_api_key())
                model = GoogleModel(
                    model_def,
                    provider=provider,
                )
        else:
            msg = f"Unknown model type: {type(model_def)}"
            raise ModelConfigurationError(msg)

        return RateLimitedModel(model)

    # Prepare models - get all available API keys
    api_keys = get_google_api_keys()
    if not api_keys:
        # Should get_google_api_keys raise if none? It's typed to return list.
        # Fallback to single getter which raises if missing
        api_keys = [get_google_api_key()]

    from egregora.llm.providers.rate_limited import RateLimitedModel

    # Helper to create model variations for all keys
    def _create_variations(model_def: str | Model) -> tuple[list[Model], list[str | None]]:
        variations: list[Model] = []
        keys_used: list[str | None] = []

        # If it's a string definition for a Google model, create one variation per key
        if isinstance(model_def, str) and model_def.startswith("google-gla:"):
            for key in api_keys:
                if use_google_batch:
                    batch_model = GoogleBatchModel(api_key=key, model_name=model_def)
                    variations.append(RateLimitedModel(batch_model))
                else:
                    variations.append(_resolve_and_wrap(model_def, api_key=key))
                keys_used.append(key)
        # For non-Google models or instances, just return single item
        # (We assume non-Google models handle their own auth or don't use these keys)
        else:
            if use_google_batch and isinstance(model_def, str) and model_def.startswith("google-gla:"):
                # Should be covered above, but just in case logic flow changes
                # If we reach here with string, it's not starting with google-gla?
                # Wait, logic above handles google-gla.
                pass

            # Use first key as default if needed, or environment
            variations.append(_resolve_and_wrap(model_def, api_key=api_keys[0]))
            keys_used.append(None)  # Unknown or managed internally

        return variations, keys_used

    # 1. Prepare Primary Variations
    # We want to try Primary with Key 1, then Primary with Key 2, etc.
    primary_variations, primary_keys = _create_variations(primary_model)
    if not primary_variations:
        # Should not happen given logic above
        raise ValueError("Failed to create primary model")

    # 2. Prepare Fallback Variations
    # For each fallback model, we try all keys
    fallback_variations: list[Model] = []
    fallback_keys: list[str | None] = []

    for m in fallback_models:
        vars_, keys_ = _create_variations(m)
        fallback_variations.extend(vars_)
        fallback_keys.extend(keys_)

    # Combine: Primary + Rest of primaries + All fallbacks
    all_models = primary_variations + fallback_variations
    all_keys = primary_keys + fallback_keys

    # Use our custom RotatingFallbackModel instead of pydantic-ai's FallbackModel
    # This rotates immediately on 429 errors rather than waiting between agent runs
    from egregora.llm.providers.rotating_fallback import RotatingFallbackModel

    return RotatingFallbackModel(all_models, model_keys=all_keys)
