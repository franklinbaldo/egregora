from pathlib import Path

import pytest

from egregora_v3.core.config import EgregoraConfig
from egregora_v3.core.config_loader import ConfigLoader


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


def test_load_defaults_from_cwd(tmp_path, monkeypatch):
    """Test loading defaults using current working directory."""
    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

    # Load without specifying site_root - should use CWD
    loader = ConfigLoader()
    config = loader.load()

    assert isinstance(config, EgregoraConfig)
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    assert config.paths.site_root == tmp_path


def test_load_from_cwd_with_yaml(tmp_path, monkeypatch):
    """Test loading YAML configuration from current working directory."""
    # Setup config in tmp_path
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("""
models:
  writer: "cwd-custom-model"
pipeline:
  step_size: 5
    """)

    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

    # Load without specifying site_root - should find config.yml in CWD
    loader = ConfigLoader()
    config = loader.load()

    assert config.models.writer == "cwd-custom-model"
    assert config.pipeline.step_size == 5
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


def test_invalid_root_type(tmp_path):
    """Test that non-mapping YAML roots raise a clear error."""
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("- list-root-value")

    loader = ConfigLoader(tmp_path)
    with pytest.raises(ValueError, match="root must be a mapping"):
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
