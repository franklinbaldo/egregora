from pathlib import Path

import pytest
import yaml

from egregora_v3.core.config import EgregoraConfig, PathsSettings


def test_default_config():
    """Test default configuration uses current working directory."""
    config = EgregoraConfig()
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    assert config.pipeline.step_unit == "days"
    # site_root defaults to CWD
    assert config.paths.site_root == Path.cwd()


def test_path_resolution(tmp_path):
    site_root = tmp_path / "mysite"
    paths = PathsSettings(site_root=site_root, posts_dir=Path("content/posts"))

    assert paths.abs_posts_dir == site_root / "content/posts"
    assert paths.abs_db_path == site_root / ".egregora/pipeline.duckdb"


def test_load_from_yaml(tmp_path):
    # Setup a mock site
    site_root = tmp_path / "mysite"
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(parents=True)

    config_data = {"pipeline": {"step_size": 7, "step_unit": "days"}, "models": {"writer": "custom-model"}}

    with (egregora_dir / "config.yml").open("w") as f:
        yaml.dump(config_data, f)

    # Load config
    config = EgregoraConfig.load(site_root)

    assert config.pipeline.step_size == 7
    assert config.models.writer == "custom-model"
    assert config.paths.site_root == site_root
    assert config.paths.abs_posts_dir == site_root / "blog/posts"


def test_load_missing_file(tmp_path):
    """Test loading from directory without config file (explicit path)."""
    site_root = tmp_path / "empty_site"
    site_root.mkdir()

    config = EgregoraConfig.load(site_root)
    assert config.pipeline.step_size == 1  # Default
    assert config.paths.site_root == site_root


def test_load_from_cwd(tmp_path, monkeypatch):
    """Test loading from current working directory (no explicit path)."""
    site_root = tmp_path / "mysite"
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(parents=True)

    config_data = {"models": {"writer": "cwd-model"}}
    with (egregora_dir / "config.yml").open("w") as f:
        yaml.dump(config_data, f)

    # Change to site directory
    monkeypatch.chdir(site_root)

    # Load without path - should use CWD
    config = EgregoraConfig.load()
    assert config.models.writer == "cwd-model"
    assert config.paths.site_root == site_root


def test_load_invalid_paths_config(tmp_path):
    site_root = tmp_path / "bad_site"
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(parents=True)

    # paths is a string, not a dict
    config_data = {"paths": "invalid_string"}

    with (egregora_dir / "config.yml").open("w") as f:
        yaml.dump(config_data, f)

    with pytest.raises(ValueError, match="Configuration 'paths' must be a dictionary"):
        EgregoraConfig.load(site_root)
