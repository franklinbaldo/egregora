import pytest
from egregora.config.settings import DEFAULT_MODEL, PipelineSettings, MAX_PROMPT_TOKENS_WARNING_THRESHOLD
from egregora.constants import KNOWN_MODEL_LIMITS
from egregora.utils.model_fallback import GOOGLE_FALLBACK_MODELS

def test_default_model_is_modern():
    """Ensure the default model is at least a 1.5-flash or 2.0 version."""
    modern_keywords = ["flash-latest", "2.0-flash", "1.5-flash", "1.5-pro", "2.0-pro"]
    assert any(kw in DEFAULT_MODEL for kw in modern_keywords), \
        f"DEFAULT_MODEL '{DEFAULT_MODEL}' seems potentially outdated or low-capacity. " \
        "Please use a flash-latest or 2.0+ model to ensure enough context for blog generation."

def test_known_model_limits_not_downgraded():
    """Ensure we don't accidentally lower the published limits of key models."""
    # We must maintain at least 1M tokens for the flagship models to avoid splitting failures
    MIN_STABLE_LIMIT = 1_000_000
    
    important_models = [
        "gemini-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-pro-latest",
        "gemini-1.5-pro",
    ]
    
    for model in important_models:
        limit = KNOWN_MODEL_LIMITS.get(model)
        assert limit is not None, f"Model {model} missing from KNOWN_MODEL_LIMITS"
        assert limit >= MIN_STABLE_LIMIT, \
            f"Context limit for {model} ({limit}) is below the required 1M stability threshold."

def test_pipeline_defaults_retain_safe_capacity():
    """Ensure default pipeline settings have a safe conservative cap."""
    settings = PipelineSettings()
    
    # max_prompt_tokens should be at least 100k for the conservative strategy
    assert settings.max_prompt_tokens >= 100_000, \
        f"max_prompt_tokens default ({settings.max_prompt_tokens}) is too low. Should be at least 100k."
        
    assert MAX_PROMPT_TOKENS_WARNING_THRESHOLD >= 100_000, \
        "MAX_PROMPT_TOKENS_WARNING_THRESHOLD should remain at 100k to match our conservative strategy."

def test_fallback_chain_is_robust():
    """Ensure fallback models are all high-capacity Gemini models."""
    modern_keywords = ["flash-latest", "2.0-flash", "1.5-flash", "pro-latest", "1.5-pro", "2.0-pro"]
    
    for model in GOOGLE_FALLBACK_MODELS:
        assert any(kw in model for kw in modern_keywords), \
            f"Fallback model '{model}' in GOOGLE_FALLBACK_MODELS is potentially low-capacity. " \
            "Downgrading to smaller models (like gemini-pro 1.0) will cause generation failures for large windows."
