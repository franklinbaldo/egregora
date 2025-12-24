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


def test_egregora_config_load_from_toml_file(tmp_path: Path):
    """It should load settings from an .egregora.toml file."""
    # Arrange
    config_content = """
[models]
writer = "custom-writer-model"
embedding = "custom-embedding-model"

[paths]
posts_dir = "blog"
"""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(config_content)

    # Act
    config = EgregoraConfig(paths__site_root=tmp_path)

    # Assert
    assert config.models.writer == "custom-writer-model"
    assert config.models.enricher == "google-gla:gemini-2.0-flash"  # Default is kept
    assert config.models.embedding == "custom-embedding-model"
    assert config.paths.posts_dir == Path("blog")
    assert config.paths.abs_posts_dir == tmp_path / "blog"


def test_egregora_config_load_with_env_var_overrides(tmp_path: Path, monkeypatch):
    """Environment variables should take precedence over the config file."""
    # Arrange
    config_content = """
[models]
writer = "file-writer-model"
enricher = "file-enricher-model"
"""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(config_content)

    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "env-writer-model")
    monkeypatch.setenv("EGREGORA_MODELS__EMBEDDING", "env-embedding-model")

    # Act
    config = EgregoraConfig(paths__site_root=tmp_path)

    # Assert
    assert config.models.writer == "env-writer-model"  # Env var wins
    assert config.models.enricher == "file-enricher-model"  # From file
    assert config.models.embedding == "env-embedding-model"  # From env var


def test_paths_settings_resolve_absolute_paths(tmp_path: Path):
    """PathsSettings should correctly resolve absolute and relative paths."""
    # Arrange
    abs_posts = tmp_path / "custom/posts"
    abs_posts.mkdir(parents=True)

    # Act
    paths = PathsSettings(site_root=tmp_path, posts_dir=Path("content"), media_dir=abs_posts)

    # Assert
    assert paths.abs_posts_dir == tmp_path / "content"
    assert paths.abs_media_dir == abs_posts
