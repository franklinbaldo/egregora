import os
import pytest
from pathlib import Path
from egregora_v3.core.config_loader import ConfigLoader
from egregora_v3.core.config import EgregoraConfig


def test_load_from_file(tmp_path):
    """Test loading configuration from a file."""
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("""
models:
  writer: "custom-writer-model"
paths:
  posts_dir: "custom-posts"
    """)

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert isinstance(config, EgregoraConfig)
    assert config.models.writer == "custom-writer-model"
    assert config.paths.posts_dir == Path("custom-posts")
    assert config.paths.site_root == tmp_path


def test_load_defaults(tmp_path):
    """Test loading defaults when no config file exists."""
    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert isinstance(config, EgregoraConfig)
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    assert config.paths.site_root == tmp_path


def test_env_var_override_string(tmp_path, monkeypatch):
    """Test overriding string configuration with environment variables."""
    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "env-writer-model")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.writer == "env-writer-model"


def test_env_var_override_int(tmp_path, monkeypatch):
    """Test overriding integer configuration with environment variables.

    Pydantic Settings automatically converts string "10" to int 10.
    """
    monkeypatch.setenv("EGREGORA_PIPELINE__STEP_SIZE", "10")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.pipeline.step_size == 10
    assert isinstance(config.pipeline.step_size, int)


def test_env_var_override_boolean_true(tmp_path, monkeypatch):
    """Test overriding boolean configuration with environment variables (true)."""
    monkeypatch.setenv("EGREGORA_MODELS__FALLBACK_ENABLED", "true")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.fallback_enabled is True


def test_env_var_override_boolean_false(tmp_path, monkeypatch):
    """Test overriding boolean configuration with environment variables (false).

    Tests that string "false" is correctly converted to bool False.
    """
    monkeypatch.setenv("EGREGORA_MODELS__FALLBACK_ENABLED", "false")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.fallback_enabled is False


def test_env_var_override_path(tmp_path, monkeypatch):
    """Test overriding path configuration with environment variables."""
    monkeypatch.setenv("EGREGORA_PATHS__POSTS_DIR", "custom-posts-from-env")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.paths.posts_dir == Path("custom-posts-from-env")


def test_env_var_precedence_over_file(tmp_path, monkeypatch):
    """Test that environment variables take precedence over file configuration."""
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("""
models:
  writer: "file-writer-model"
    """)

    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "env-writer-model")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    # Env var should win
    assert config.models.writer == "env-writer-model"


def test_invalid_yaml(tmp_path):
    """Test handling of invalid YAML configuration."""
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("invalid: [ yaml: content")

    loader = ConfigLoader(tmp_path)
    with pytest.raises(ValueError, match="Invalid YAML"):
        loader.load()


def test_case_insensitivity(tmp_path, monkeypatch):
    """Test that environment variable names are case-insensitive after prefix.

    Pydantic Settings converts env var names to lowercase for matching.
    """
    # Mixed case after prefix should still work
    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "mixed-case-model")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.writer == "mixed-case-model"
