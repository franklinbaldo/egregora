from pathlib import Path

from egregora_v3.core.config import EgregoraConfig, PathsSettings


def test_default_config():
    """Test default configuration uses current working directory."""
    config = EgregoraConfig()
    assert config.models.writer == "google-gla:gemini-2.0-flash"
    # site_root defaults to CWD
    assert config.paths.site_root == Path.cwd()


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
writer = "custom-model"
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
