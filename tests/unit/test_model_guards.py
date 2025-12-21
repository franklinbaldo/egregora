from egregora.config.settings import DEFAULT_MODEL


def test_default_model_is_modern():
    """
    Ensure the default model is a modern, high-capacity model.
    We verify it's not a legacy 1.0 model.
    """
    model = DEFAULT_MODEL.lower()

    # Must be Flash or Pro
    assert "flash" in model or "pro" in model

    # Must NOT be legacy 1.0
    assert "1.0" not in model
    assert model.replace("google-gla:", "").replace("models/", "") != "gemini-pro"


def test_model_params_defaults(config_factory):
    """Ensure default configuration parameters meet safety requirements."""
    # Create a default config
    config = config_factory()

    # verify writer model defaults matches our verified default
    assert config.models.writer == DEFAULT_MODEL
