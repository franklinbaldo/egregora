import os
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from egregora_v3.core.config import EgregoraConfig, ModelSettings, PathsSettings


@pytest.fixture(autouse=True)
def chdir_to_tmp_path(tmp_path: Path):
    """Ensure tests run in a clean directory."""
    original_dir = Path.cwd()
    os.chdir(tmp_path)
    yield
    os.chdir(original_dir)


def test_egregora_config_load_defaults(tmp_path: Path):
    """It should load default settings when no config file or env vars are present."""
    # Act
    # We now pass a paths__site_root to override the default Path.cwd()
    # for predictable testing.
    config = EgregoraConfig(paths__site_root=tmp_path)

    # Assert
    assert isinstance(config.models, ModelSettings)
    assert isinstance(config.paths, PathsSettings)
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    assert config.paths.site_root == tmp_path
    assert config.paths.posts_dir == Path("posts")
    assert config.paths.abs_posts_dir == tmp_path / "posts"


def test_path_construction(tmp_path):
    """Test explicit path construction."""
    site_root = tmp_path / "mysite"
    paths = PathsSettings(site_root=site_root, posts_dir=Path("content/posts"))

    # Explicit is better than implicit.
    # The caller is responsible for joining the paths.
    assert paths.site_root / paths.posts_dir == site_root / "content/posts"
    assert paths.site_root / paths.db_path == site_root / ".egregora/pipeline.duckdb"


def test_load_from_toml(tmp_path, monkeypatch):
    """Test loading from .egregora.toml in the current directory."""
    site_root = tmp_path / "mysite"
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "custom-writer-model"
embedding = "custom-embedding-model"
"""
    )
    monkeypatch.chdir(site_root)
    config = EgregoraConfig()

    assert config.models.writer == "custom-model"
    assert config.paths.site_root == site_root
    assert config.paths.site_root / config.paths.posts_dir == site_root / "posts"


def test_load_missing_file(tmp_path, monkeypatch):
    """Test loading from directory without config file."""
    site_root = tmp_path / "empty_site"
    site_root.mkdir()

    monkeypatch.chdir(site_root)
    config = EgregoraConfig()

    assert config.models.writer == "google-gla:gemini-2.0-flash"  # Default
    assert config.paths.site_root == site_root


def test_declarative_load_from_toml(tmp_path, monkeypatch):
    """Test declarative loading from .egregora.toml."""
    site_root = tmp_path / "declarative_site"
    site_root.mkdir(parents=True)

    config_file = site_root / ".egregora.toml"
    config_file.write_text(
        """
[models]
writer = "declarative-model"
[paths]
posts_dir = "declarative_posts"
        """
    )
    monkeypatch.chdir(site_root)

    # Load config declaratively
    config = EgregoraConfig()

    assert config.models.writer == "declarative-model"
    assert config.paths.posts_dir == Path("declarative_posts")
    assert config.paths.site_root == site_root
