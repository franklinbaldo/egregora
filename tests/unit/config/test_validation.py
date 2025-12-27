"""Tests for configuration validation CLI commands."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from egregora.config.exceptions import (
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    InvalidDateFormatError,
    InvalidRetrievalModeError,
    InvalidTimezoneError,
    SiteNotFoundError,
)
from egregora.config.settings import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_MODEL,
    EgregoraConfig,
    find_egregora_config,
    load_egregora_config,
    parse_date_arg,
    save_egregora_config,
    validate_retrieval_config,
    validate_timezone,
)


def test_config_validate_with_valid_config(tmp_path: Path):
    """Test config validation with a valid configuration."""
    config_file = tmp_path / ".egregora.toml"

    # Write valid config using defaults
    config_file.write_text(
        f"""
[models]
writer = "{DEFAULT_MODEL}"
embedding = "{DEFAULT_EMBEDDING_MODEL}"

[rag]
enabled = true
top_k = 5
""".lstrip()
    )

    # Load and validate
    config = load_egregora_config(tmp_path)
    assert config.models.writer == DEFAULT_MODEL
    assert config.rag.enabled is True


def test_config_validate_with_invalid_model_format(tmp_path: Path):
    """Test config validation catches invalid model format."""
    config_file = tmp_path / ".egregora.toml"

    # Write invalid config (missing google-gla: prefix)
    config_file.write_text(
        """
[models]
writer = "gemini-flash-latest"
""".lstrip()
    )

    # Should raise ConfigValidationError
    with pytest.raises(ConfigValidationError):
        load_egregora_config(tmp_path)


def test_config_validate_model_name_validator():
    """Test model name format validators."""
    # Valid formats using defaults
    config = EgregoraConfig(models={"writer": DEFAULT_MODEL, "embedding": DEFAULT_EMBEDDING_MODEL})
    assert config.models.writer == DEFAULT_MODEL
    assert config.models.embedding == DEFAULT_EMBEDDING_MODEL

    # Invalid Pydantic-AI format (missing prefix)
    with pytest.raises(ValidationError) as exc:
        EgregoraConfig(models={"writer": "gemini-flash-latest"})
    assert "Invalid Pydantic-AI model format" in str(exc.value)

    # NOTE: Embedding model validation is handled by EmbeddingProviderFactory at runtime,
    # not at config load time. This allows for flexible provider support via strategy pattern.


def test_config_validate_cross_field_rag_requires_lancedb():
    """Test cross-field validation: RAG requires lancedb_dir."""
    # RAG enabled but lancedb_dir empty - should fail
    with pytest.raises(ValidationError) as exc:
        EgregoraConfig(rag={"enabled": True}, paths={"lancedb_dir": ""})
    assert "lancedb_dir is not set" in str(exc.value)


def test_config_rag_top_k_bounds():
    """Test RAG top_k has proper bounds."""
    # Valid top_k
    config = EgregoraConfig(rag={"top_k": 5})
    assert config.rag.top_k == 5

    # Top_k at maximum
    config = EgregoraConfig(rag={"top_k": 20})
    assert config.rag.top_k == 20

    # Top_k below minimum
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"top_k": 0})

    # Top_k above maximum
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"top_k": 21})


def test_config_creates_default_if_missing(tmp_path: Path):
    """Test config loader creates default if file missing."""
    # No config file present
    config = load_egregora_config(tmp_path)

    # Should return default config
    assert config.models.writer == DEFAULT_MODEL
    assert config.models.embedding == DEFAULT_EMBEDDING_MODEL
    assert config.rag.enabled is True

    # Should have created the file
    config_file = tmp_path / ".egregora.toml"
    assert config_file.exists()


def test_config_toml_roundtrip(tmp_path: Path):
    """Test config can be saved and loaded."""
    # Create config with non-default values
    custom_model = "google-gla:gemini-pro-latest"
    config = EgregoraConfig(
        models={"writer": custom_model},
        rag={"enabled": False, "top_k": 10},
    )

    # Save to file
    save_egregora_config(config, tmp_path)

    # Load back
    loaded = load_egregora_config(tmp_path)

    assert loaded.models.writer == custom_model
    assert loaded.rag.enabled is False
    assert loaded.rag.top_k == 10


def test_config_load_from_cwd(tmp_path: Path, monkeypatch):
    """Test loading config from current working directory."""
    # Create config in tmp_path
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "google-gla:gemini-pro-latest"

[rag]
enabled = false
""".lstrip()
    )

    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

    # Load without specifying site_root - should use CWD
    config = load_egregora_config()

    assert config.models.writer == "google-gla:gemini-pro-latest"
    assert config.rag.enabled is False


def test_config_env_var_override_string(tmp_path: Path, monkeypatch):
    """Test environment variable override for string values."""
    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "google-gla:gemini-experimental")

    # Create minimal config file
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text('[models]\nwriter = "google-gla:gemini-flash-latest"\n')

    config = load_egregora_config(tmp_path)

    # Env var should override file value
    assert config.models.writer == "google-gla:gemini-experimental"


def test_config_env_var_override_boolean(tmp_path: Path, monkeypatch):
    """Test environment variable override for boolean values."""
    monkeypatch.setenv("EGREGORA_RAG__ENABLED", "false")

    config_file = tmp_path / ".egregora.toml"
    config_file.write_text("[rag]\nenabled = true\n")

    config = load_egregora_config(tmp_path)

    # Env var should override file value
    assert config.rag.enabled is False


def test_config_env_var_override_integer(tmp_path: Path, monkeypatch):
    """Test environment variable override for integer values."""
    monkeypatch.setenv("EGREGORA_RAG__TOP_K", "15")

    config_file = tmp_path / ".egregora.toml"
    config_file.write_text("[rag]\ntop_k = 5\n")

    config = load_egregora_config(tmp_path)

    # Env var should override file value
    assert config.rag.top_k == 15
    assert isinstance(config.rag.top_k, int)


def test_config_multi_site_selection(tmp_path: Path):
    """Ensure multi-site configs can be selected explicitly."""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(
        """
[sites.primary.models]
writer = "google-gla:gemini-pro-latest"

[sites.secondary.models]
writer = "google-gla:gemini-2.5-flash"
""".lstrip()
    )

    primary = load_egregora_config(tmp_path, site="primary")
    secondary = load_egregora_config(tmp_path, site="secondary")

    assert primary.models.writer == "google-gla:gemini-pro-latest"
    assert secondary.models.writer == "google-gla:gemini-2.5-flash"


def test_config_requires_at_least_one_site(tmp_path: Path):
    """Validate that at least one site entry is present."""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text("sites = {}")

    with pytest.raises(ConfigError, match="at least one site"):
        load_egregora_config(tmp_path)


def test_config_unknown_site(tmp_path: Path):
    """Unknown site selections should fail fast."""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(
        """
[sites.default.models]
writer = "google-gla:gemini-pro-latest"
""".lstrip()
    )

    with pytest.raises(SiteNotFoundError, match="not found"):
        load_egregora_config(tmp_path, site="does-not-exist")


def test_find_config_raises_not_found(tmp_path: Path):
    """Test that find_egregora_config raises when no config is found."""
    # Start search in an empty directory
    with pytest.raises(ConfigNotFoundError):
        find_egregora_config(tmp_path)


def test_parse_date_arg_invalid_format():
    """Test that parse_date_arg raises InvalidDateFormatError for invalid formats."""
    with pytest.raises(InvalidDateFormatError):
        parse_date_arg("2023-13-01")  # Invalid month
    with pytest.raises(InvalidDateFormatError):
        parse_date_arg("not-a-date")


def test_validate_timezone_invalid_timezone():
    """Test that validate_timezone raises InvalidTimezoneError for invalid timezones."""
    with pytest.raises(InvalidTimezoneError):
        validate_timezone("Invalid/Timezone")


def test_validate_retrieval_config_invalid_mode():
    """Test that validate_retrieval_config raises InvalidRetrievalModeError for invalid modes."""
    with pytest.raises(InvalidRetrievalModeError):
        validate_retrieval_config("invalid_mode")
