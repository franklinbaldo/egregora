from pathlib import Path

import pytest

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


def test_load_from_toml(tmp_path):
    # Setup a mock site
    site_root = tmp_path / "mysite"
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text(
        """
[pipeline]
step_size = 7
step_unit = "days"

[models]
writer = "custom-model"
        """
    )

    # Load config
    config = EgregoraConfig.load(site_root)

    assert config.pipeline.step_size == 7
    assert config.models.writer == "custom-model"
    assert config.paths.site_root == site_root
    assert config.paths.abs_posts_dir == site_root / "posts"


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
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "cwd-model"
        """
    )

    # Change to site directory
    monkeypatch.chdir(site_root)

    # Load without path - should use CWD
    config = EgregoraConfig.load()
    assert config.models.writer == "cwd-model"
    assert config.paths.site_root == site_root


def test_load_invalid_paths_config(tmp_path):
    site_root = tmp_path / "bad_site"
    site_root.mkdir(parents=True)

    # paths is a string, not a dict
    config_file = site_root / ".egregora.toml"
    config_file.write_text('paths = "invalid_string"')

    with pytest.raises(TypeError, match="Configuration 'paths' must be a dictionary"):
        EgregoraConfig.load(site_root)
