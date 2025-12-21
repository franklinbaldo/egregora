from egregora.config.settings import DEFAULT_MODEL, EgregoraConfig

def test_model_guards():
    """Ensure we are using modern Gemini models."""
    modern_keywords = ["flash", "pro", "1.5", "2.0"]
    is_modern = any(k in DEFAULT_MODEL for k in modern_keywords)
    assert is_modern, f"DEFAULT_MODEL {DEFAULT_MODEL} appears outdated"
    assert "1.0" not in DEFAULT_MODEL, "Should not use 1.0 models"

def test_model_params_defaults(config_factory):
    """Ensure defaults are robust."""
    config = config_factory()
    assert config.models.writer == DEFAULT_MODEL
    assert config.pipeline.max_prompt_tokens >= 1_000_000
