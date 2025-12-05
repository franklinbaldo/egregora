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

def test_env_var_override(tmp_path, monkeypatch):
    """Test overriding configuration with environment variables."""
    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "env-writer-model")
    monkeypatch.setenv("EGREGORA_PIPELINE__STEP_SIZE", "10")

    loader = ConfigLoader(tmp_path)
    config = loader.load()

    assert config.models.writer == "env-writer-model"
    assert config.pipeline.step_size == 10

def test_invalid_yaml(tmp_path):
    """Test handling of invalid YAML configuration."""
    config_dir = tmp_path / ".egregora"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    config_file.write_text("invalid: [ yaml: content")

    loader = ConfigLoader(tmp_path)
    with pytest.raises(ValueError, match="Invalid YAML"):
        loader.load()
