from egregora.config.settings import DEFAULT_MODEL


def test_default_model_is_modern():
    """Ensure the default model is at least a 2.5 version."""
    modern_keywords = [
        "flash-latest",
        "2.5-flash",
        "pro-latest",
        "2.5-pro",
    ]
    assert any(kw in DEFAULT_MODEL for kw in modern_keywords), (
        f"DEFAULT_MODEL '{DEFAULT_MODEL}' seems outdated. "
        "Please use a flash-latest or 2.5+ model."
    )


def test_model_params_defaults(config_factory):
    """Ensure default configuration parameters meet safety requirements."""
    # Create a default config
    config = config_factory()

    # verify writer model defaults matches our verified default
    assert config.models.writer == DEFAULT_MODEL
