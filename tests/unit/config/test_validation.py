"""Tests for configuration validation CLI commands."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from egregora.config.settings import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_MODEL,
    EgregoraConfig,
    load_egregora_config,
)


def test_config_validate_with_valid_config(tmp_path: Path):
    """Test config validation with a valid configuration."""
    # Create config directory
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"

    # Write valid config using defaults
    config_file.write_text(
        f"""
models:
  writer: {DEFAULT_MODEL}
  embedding: {DEFAULT_EMBEDDING_MODEL}

rag:
  enabled: true
  top_k: 5

privacy:
  enabled: true
  pii_action: warn
"""
    )

    # Load and validate
    config = load_egregora_config(tmp_path)
    assert config.models.writer == DEFAULT_MODEL
    assert config.rag.enabled is True
    assert config.privacy.enabled is True


def test_config_validate_with_invalid_model_format(tmp_path: Path):
    """Test config validation catches invalid model format."""
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"

    # Write invalid config (missing google-gla: prefix)
    config_file.write_text(
        """
models:
  writer: gemini-flash-latest
"""
    )

    # Should create default config on validation error
    config = load_egregora_config(tmp_path)
    # Returns default config on error
    assert config.models.writer == DEFAULT_MODEL


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

    # Invalid embedding format (missing models/ prefix)
    with pytest.raises(ValidationError) as exc:
        EgregoraConfig(models={"embedding": "gemini-embedding-001"})
    assert "Invalid Google GenAI model format" in str(exc.value)


def test_config_validate_cross_field_rag_requires_lancedb():
    """Test cross-field validation: RAG requires lancedb_dir."""
    # RAG enabled but lancedb_dir empty - should fail
    with pytest.raises(ValidationError) as exc:
        EgregoraConfig(rag={"enabled": True}, paths={"lancedb_dir": ""})
    assert "lancedb_dir is not set" in str(exc.value)


def test_config_privacy_settings_defaults(minimal_config):
    """Test privacy settings have secure defaults."""
    config = minimal_config

    # Test new two-level privacy structure
    assert config.privacy.structural.enabled is True
    assert config.privacy.structural.author_strategy.value == "uuid_mapping"
    assert config.privacy.pii_prevention.writer.enabled is True
    assert config.privacy.pii_prevention.writer.scope.value == "all_pii"
    assert config.privacy.pii_prevention.enricher.enabled is True

    # Test backward compatibility
    assert config.privacy.enabled is True  # Maps to structural.enabled
    assert config.privacy.anonymize_authors is True  # Author strategy != NONE


def test_config_privacy_settings_configurable():
    """Test privacy settings can be configured."""
    config = EgregoraConfig(
        privacy={
            "structural": {
                "enabled": False,
                "author_strategy": "none",
            },
            "pii_prevention": {
                "writer": {
                    "enabled": False,
                },
                "enricher": {
                    "enabled": False,
                },
            },
        }
    )

    assert config.privacy.structural.enabled is False
    assert config.privacy.structural.author_strategy.value == "none"
    assert config.privacy.pii_prevention.writer.enabled is False
    assert config.privacy.pii_prevention.enricher.enabled is False

    # Test backward compatibility
    assert config.privacy.enabled is False  # Maps to structural.enabled
    assert config.privacy.anonymize_authors is False  # Author strategy == NONE


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
    # No .egregora directory
    config = load_egregora_config(tmp_path)

    # Should return default config
    assert config.models.writer == DEFAULT_MODEL
    assert config.models.embedding == DEFAULT_EMBEDDING_MODEL
    assert config.rag.enabled is True

    # Should have created the file
    config_file = tmp_path / ".egregora" / "config.yml"
    assert config_file.exists()


def test_config_yaml_roundtrip(tmp_path: Path):
    """Test config can be saved and loaded."""
    from egregora.config.settings import save_egregora_config

    # Create config with non-default values
    custom_model = "google-gla:gemini-pro-latest"
    config = EgregoraConfig(
        models={"writer": custom_model},
        rag={"enabled": False, "top_k": 10},
        privacy={"structural": {"enabled": False}},
    )

    # Save to file
    save_egregora_config(config, tmp_path)

    # Load back
    loaded = load_egregora_config(tmp_path)

    assert loaded.models.writer == custom_model
    assert loaded.rag.enabled is False
    assert loaded.rag.top_k == 10
    assert loaded.privacy.structural.enabled is False
    assert loaded.privacy.enabled is False  # Backward compat property


def test_config_load_from_cwd(tmp_path: Path, monkeypatch):
    """Test loading config from current working directory."""
    # Create config in tmp_path
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text(
        """
models:
  writer: google-gla:gemini-pro-latest
rag:
  enabled: false
"""
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
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("models:\n  writer: google-gla:gemini-flash-latest\n")

    config = load_egregora_config(tmp_path)

    # Env var should override file value
    assert config.models.writer == "google-gla:gemini-experimental"


def test_config_env_var_override_boolean(tmp_path: Path, monkeypatch):
    """Test environment variable override for boolean values."""
    monkeypatch.setenv("EGREGORA_RAG__ENABLED", "false")

    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("rag:\n  enabled: true\n")

    config = load_egregora_config(tmp_path)

    # Env var should override file value
    assert config.rag.enabled is False


def test_config_env_var_override_integer(tmp_path: Path, monkeypatch):
    """Test environment variable override for integer values."""
    monkeypatch.setenv("EGREGORA_RAG__TOP_K", "15")

    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("rag:\n  top_k: 5\n")

    config = load_egregora_config(tmp_path)

    # Env var should override file value
    assert config.rag.top_k == 15
    assert isinstance(config.rag.top_k, int)
